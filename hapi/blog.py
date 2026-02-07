"""HubSpot Blog API v1 client module.

Provides the BlogClient class for interacting with HubSpot's Blog API,
supporting CRUD operations on blogs, blog posts, comments, and topics.
All HTTP communication routes through BaseClient (see hapi/base.py),
which provides retry logic with exponential backoff, authentication
injection (API key or OAuth), and gzip response handling.

Public methods:
    - get_blogs: List all blogs for the portal.
    - get_blog_info: Retrieve metadata for a single blog.
    - get_posts: List posts for a given blog.
    - get_draft_posts: List draft posts for a given blog.
    - get_published_posts: List published posts for a given blog.
    - get_pulished_posts: Backward-compatible misspelling alias
        for get_published_posts.
    - get_blog_comments: List comments on a blog.
    - get_post: Retrieve a single post by GUID.
    - get_post_comments: List comments on a specific post.
    - get_comment: Retrieve a single comment by GUID.
    - create_post: Create a new blog post.
    - update_post: Update an existing blog post.
    - publish_post: Publish or unpublish a blog post.
    - create_comment: Create a comment on a blog post.

Usage example::

    from hapi.blog import BlogClient
    client = BlogClient(api_key='demo')
    blogs = client.get_blogs()
"""
from base import BaseClient
import simplejson as json

BLOG_API_VERSION = '1'

class BlogClient(BaseClient):
    """Client for HubSpot Blog API v1 providing CRUD operations on blogs, posts, and comments.

    Inherits from BaseClient which supplies the core HTTP engine including
    retry logic with exponential backoff, authentication injection (API key
    as query parameter or OAuth access token), gzip response decompression,
    and JSON result parsing.

    All endpoint paths are constructed via _get_path(), which prefixes
    subpaths with 'blog/v1/' using the module-level BLOG_API_VERSION
    constant. Requests are dispatched through BaseClient._call() for
    parsed JSON responses, or through BaseClient._call_raw() for raw
    HTTP response objects.

    Attributes:
        Inherits from BaseClient:
            api_key (str): HubSpot API key for authentication.
            access_token (str): OAuth access token (alternative to api_key).
            options (dict): Merged configuration including api_base, timeout,
                connection_type, and protocol.
            log (logging.Logger): Logger instance for request diagnostics.
    """
  
    def _get_path(self, subpath):
        """Construct the fully qualified Blog API v1 path for a given subpath.

        Prepends the Blog API version prefix to the provided subpath,
        producing a path like 'blog/v1/list.json' that
        BaseClient._prepare_request() uses to build the complete
        request URL.

        Args:
            subpath (str): The API-specific path segment (e.g.,
                'list.json', '{blog_guid}/posts.json').

        Returns:
            str: The versioned blog API path in the format
                'blog/v{BLOG_API_VERSION}/{subpath}'.
        """
        return 'blog/v%s/%s' % (BLOG_API_VERSION, subpath)
    
    def get_blogs(self, **options):
        """Retrieve a list of all blogs for the authenticated portal.

        Endpoint Access:
            HTTP Method: GET
            URL: /blog/v1/list.json
            Auth: API key injected as 'hapikey' query parameter
                by BaseClient, or OAuth access_token.
            Body: None (GET request).
            Response: JSON list of blog objects, each containing
                blog metadata (guid, name, etc.).

        Args:
            **options: Additional keyword arguments passed through to
                BaseClient._call() (e.g., timeout, number_retries).

        Returns:
            dict or list: Parsed JSON response from the HubSpot Blog
                API containing blog listing data.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        return self._call('list.json', **options)
    
    def get_blog_info(self, blog_guid, **options):
        """Retrieve metadata for a single blog identified by its GUID.

        Endpoint Access:
            HTTP Method: GET
            URL: /blog/v1/{blog_guid}
            Auth: API key or OAuth access_token via BaseClient.
            Body: None (GET request).
            Response: JSON dict containing blog metadata (name,
                created, updated, etc.).

        Args:
            blog_guid (str): The unique identifier (GUID) of the blog
                to retrieve.
            **options: Additional keyword arguments passed through to
                BaseClient._call().

        Returns:
            dict: Parsed JSON response containing the blog's metadata.

        Raises:
            HapiError: When the API returns a non-2xx status code.
            HapiNotFound: When the specified blog_guid does not exist.
        """
        return self._call(blog_guid, **options)
    
    def get_posts(self, blog_guid, **options):
        """Retrieve all posts for a specific blog.

        Endpoint Access:
            HTTP Method: GET
            URL: /blog/v1/{blog_guid}/posts.json
            Auth: API key or OAuth access_token via BaseClient.
            Body: None (GET request).
            Response: JSON list of post objects for the specified blog.

        Args:
            blog_guid (str): The unique identifier of the blog whose
                posts to retrieve.
            **options: Additional keyword arguments passed through to
                BaseClient._call() (e.g., limit, offset).

        Returns:
            list: Parsed JSON response containing blog post objects.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        return self._call('%s/posts.json' % blog_guid, **options)
    
    def get_draft_posts(self, blog_guid, **options):
        """Retrieve only draft (unpublished) posts for a specific blog.

        Send the draft=true query parameter to filter results to
        unpublished posts only. Unlike get_published_posts, this method
        passes params and **options separately to BaseClient._call(),
        so caller-supplied options do not interfere with the draft filter.

        Endpoint Access:
            HTTP Method: GET
            URL: /blog/v1/{blog_guid}/posts.json?draft=true
            Auth: API key or OAuth access_token via BaseClient.
            Body: None (GET request).
            Response: JSON list of draft post objects.

        Args:
            blog_guid (str): The unique identifier of the blog whose
                draft posts to retrieve.
            **options: Additional keyword arguments passed through to
                BaseClient._call().

        Returns:
            list: Parsed JSON response containing only draft post
                objects.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        return self._call('%s/posts.json' % blog_guid, params={'draft': 'true'}, **options)

    def get_published_posts(self, blog_guid, **options):
        """Retrieve only published posts for a specific blog.

        Construct a params dict with draft=false, then merge the caller's
        **options into that dict before passing it to BaseClient._call().

        Endpoint Access:
            HTTP Method: GET
            URL: /blog/v1/{blog_guid}/posts.json?draft=false
            Auth: API key or OAuth access_token via BaseClient.
            Body: None (GET request).
            Response: JSON list of published post objects.

        Args:
            blog_guid (str): The unique identifier of the blog whose
                published posts to retrieve.
            **options: Additional keyword arguments merged into the
                params dict. Note that these options become query
                parameters, not BaseClient._call() options.

        Returns:
            list: Parsed JSON response containing only published post
                objects.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        # Why: [Trade-offs] — Options are merged into params dict rather than passed
        # as **options to _call, which means options override the draft=false filter
        # if a caller passes a conflicting 'draft' key. This differs from
        # get_draft_posts which keeps params separate from **options. This design
        # accepts the risk of accidental filter override in exchange for allowing
        # callers to add arbitrary query parameters alongside the draft filter.
        params = dict(draft='false')
        params.update(options)
        return self._call('%s/posts.json' % blog_guid, params=params)

    # Why: [Trade-offs] — The method name 'get_pulished_posts' contains a misspelling
    # but is retained as a backward-compatible alias to avoid breaking existing API
    # consumers who depend on this method name. Correcting the spelling would
    # constitute a breaking API change.
    def get_pulished_posts(self, blog_guid, **options):
        """Retrieve published posts for a blog (backward-compatible misspelling alias).

        This method is a backward-compatible alias for get_published_posts
        with a misspelled name ('pulished' instead of 'published'). It is
        retained to avoid breaking existing consumers who depend on this
        method name. New code should use get_published_posts instead.

        Unlike get_published_posts, this implementation passes params and
        **options separately to BaseClient._call(), matching the pattern
        used by get_draft_posts.

        Endpoint Access:
            HTTP Method: GET
            URL: /blog/v1/{blog_guid}/posts.json?draft=false
            Auth: API key or OAuth access_token via BaseClient.
            Body: None (GET request).
            Response: JSON list of published post objects.

        Args:
            blog_guid (str): The unique identifier of the blog whose
                published posts to retrieve.
            **options: Additional keyword arguments passed through to
                BaseClient._call().

        Returns:
            list: Parsed JSON response containing only published post
                objects.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        return self._call('%s/posts.json' % blog_guid, params={'draft': 'false'}, **options)
    
    def get_blog_comments(self, blog_guid, **options):
        """Retrieve all comments for a specific blog.

        Endpoint Access:
            HTTP Method: GET
            URL: /blog/v1/{blog_guid}/comments.json
            Auth: API key or OAuth access_token via BaseClient.
            Body: None (GET request).
            Response: JSON list of comment objects for the specified
                blog.

        Args:
            blog_guid (str): The unique identifier of the blog whose
                comments to retrieve.
            **options: Additional keyword arguments passed through to
                BaseClient._call().

        Returns:
            list: Parsed JSON response containing comment objects.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        return self._call('%s/comments.json' % blog_guid, **options)
    
    def get_post(self, post_guid, **options):
        """Retrieve a single blog post identified by its GUID.

        Endpoint Access:
            HTTP Method: GET
            URL: /blog/v1/posts/{post_guid}.json
            Auth: API key or OAuth access_token via BaseClient.
            Body: None (GET request).
            Response: JSON dict containing post data (title, body,
                author, tags, metadata, etc.).

        Args:
            post_guid (str): The unique identifier (GUID) of the blog
                post to retrieve.
            **options: Additional keyword arguments passed through to
                BaseClient._call().

        Returns:
            dict: Parsed JSON response containing the blog post data.

        Raises:
            HapiError: When the API returns a non-2xx status code.
            HapiNotFound: When the specified post_guid does not exist.
        """
        return self._call('posts/%s.json' % post_guid, **options)
    
    def get_post_comments(self, post_guid, **options):
        """Retrieve all comments for a specific blog post.

        Endpoint Access:
            HTTP Method: GET
            URL: /blog/v1/posts/{post_guid}/comments.json
            Auth: API key or OAuth access_token via BaseClient.
            Body: None (GET request).
            Response: JSON list of comment objects for the specified
                post.

        Args:
            post_guid (str): The unique identifier (GUID) of the blog
                post whose comments to retrieve.
            **options: Additional keyword arguments passed through to
                BaseClient._call().

        Returns:
            list: Parsed JSON response containing comment objects for
                the specified post.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        return self._call('posts/%s/comments.json' % post_guid, **options)
    
    def get_comment(self, comment_guid, **options):
        """Retrieve a single comment identified by its GUID.

        Endpoint Access:
            HTTP Method: GET
            URL: /blog/v1/comments/{comment_guid}.json
            Auth: API key or OAuth access_token via BaseClient.
            Body: None (GET request).
            Response: JSON dict containing comment data (author,
                content, timestamp, etc.).

        Args:
            comment_guid (str): The unique identifier (GUID) of the
                comment to retrieve.
            **options: Additional keyword arguments passed through to
                BaseClient._call().

        Returns:
            dict: Parsed JSON response containing the comment data.

        Raises:
            HapiError: When the API returns a non-2xx status code.
            HapiNotFound: When the specified comment_guid does not
                exist.
        """
        return self._call('comments/%s.json' % comment_guid, **options)
    
    def create_post(self, blog_guid, author_name, author_email, title, summary, content, tags, meta_desc, meta_keyword, **options):
        """Create a new blog post under the specified blog.

        Serialize post data as a JSON payload and send it via POST to
        the blog posts endpoint. The response is processed through
        BaseClient._call() which applies _digest_result() for JSON
        parsing of the response body.

        The JSON payload maps Python parameter names to HubSpot's
        expected camelCase field names:
            - title -> title
            - author_name -> authorDisplayName
            - author_email -> authorEmail
            - summary -> summary
            - content -> body
            - tags -> tags (list)
            - meta_desc -> metaDescription
            - meta_keyword -> metaKeywords

        Endpoint Access:
            HTTP Method: POST
            URL: /blog/v1/{blog_guid}/posts.json
            Auth: API key or OAuth access_token via BaseClient.
            Body: JSON-encoded dict with keys: title,
                authorDisplayName, authorEmail, summary, body,
                tags, metaDescription, metaKeywords.
            Response: Created post data, parsed by _digest_result().

        Args:
            blog_guid (str): The unique identifier of the blog to
                create the post under.
            author_name (str): Display name of the post author,
                mapped to 'authorDisplayName' in the API payload.
            author_email (str): Email address of the post author,
                mapped to 'authorEmail' in the API payload.
            title (str): Title of the blog post.
            summary (str): Short summary or excerpt of the blog post.
            content (str): Full HTML body content of the blog post,
                mapped to 'body' in the API payload.
            tags (list): List of tag strings to associate with the
                post.
            meta_desc (str): Meta description for SEO, mapped to
                'metaDescription' in the API payload.
            meta_keyword (str): Meta keywords for SEO, mapped to
                'metaKeywords' in the API payload.
            **options: Additional keyword arguments passed through to
                BaseClient._call().

        Returns:
            dict or str: The API response, parsed as a dict if the
                response body is valid JSON, otherwise the raw
                response body string.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        post = json.dumps(dict(
            title = title, 
            authorDisplayName = author_name, 
            authorEmail = author_email, 
            summary = summary, 
            body = content, 
            tags = tags, 
            metaDescription = meta_desc, 
            metaKeywords = meta_keyword))
        # Why: [Assumptions Made] — content_type='application/json' is explicitly set
        # because BaseClient defaults to URL-encoded form data; blog post creation
        # requires JSON serialization of complex nested structures (tags array,
        # metadata fields).
        raw_response = self._call('%s/posts.json' % blog_guid, data=post, method='POST', content_type='application/json', raw_output=True, **options)
        return raw_response
    
    def update_post(self, post_guid, title=None, summary=None, content=None, meta_desc=None, meta_keyword=None, tags=None, **options):
        """Update an existing blog post with the specified fields.

        Use a translation dict to map Python-style parameter names to
        HubSpot's camelCase API field names. Only non-None parameters
        are included in the update payload, allowing partial updates.

        The update_param_translation mapping:
            - title -> title
            - summary -> summary
            - content -> body
            - meta_desc -> metaDescription
            - meta_keyword -> metaKeywords
            - tags -> tags

        Endpoint Access:
            HTTP Method: PUT
            URL: /blog/v1/posts/{post_guid}.json
            Auth: API key or OAuth access_token via BaseClient.
            Body: JSON-encoded dict containing only the fields being
                updated, with camelCase keys matching HubSpot's API
                contract.
            Response: Updated post data, parsed by _digest_result().

        Args:
            post_guid (str): The unique identifier (GUID) of the post
                to update.
            title (str, optional): New title for the blog post.
                Defaults to None (not updated).
            summary (str, optional): New summary for the blog post.
                Defaults to None (not updated).
            content (str, optional): New HTML body content, mapped to
                'body' in the API payload. Defaults to None (not
                updated).
            meta_desc (str, optional): New meta description, mapped
                to 'metaDescription'. Defaults to None (not updated).
            meta_keyword (str, optional): New meta keywords, mapped
                to 'metaKeywords'. Defaults to None (not updated).
            tags (list, optional): New list of tag strings. Defaults
                to None, which is normalized to an empty list before
                processing.
            **options: Additional keyword arguments passed through to
                BaseClient._call().

        Returns:
            dict or str: The API response, parsed as a dict if the
                response body is valid JSON, otherwise the raw
                response body string.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        tags = tags or []
        # Why: [Alternatives Considered] — The update_param_translation dict maps
        # Python-style parameter names to HubSpot's camelCase API field names rather
        # than requiring callers to use camelCase directly, providing a Pythonic
        # interface while maintaining API compatibility.
        update_param_translation = dict(title='title', summary='summary', content='body', meta_desc='metaDescription', meta_keyword='metaKeywords', tags='tags')
        post_dict = dict([(k,locals()[p]) for p,k in update_param_translation.iteritems() if locals().get(p)])
        post = json.dumps(post_dict)
        raw_response = self._call('posts/%s.json' % post_guid, data=post, method='PUT', content_type='application/json', raw_output=True, **options)
        return raw_response

    def publish_post(self, post_guid, should_notify, publish_time = None, is_draft = 'false', **options):
        """Publish, unpublish, or schedule a blog post.

        Send a JSON payload with publication state fields to control
        the post's publish status. The same endpoint (PUT to the post
        URL) is used for both publishing and unpublishing by toggling
        the 'draft' field.

        Endpoint Access:
            HTTP Method: PUT
            URL: /blog/v1/posts/{post_guid}.json
            Auth: API key or OAuth access_token via BaseClient.
            Body: JSON-encoded dict with keys:
                - published: Timestamp for scheduled publishing
                    (or None for immediate).
                - draft: 'true' to unpublish, 'false' to publish.
                - sendNotifications: Whether to send subscriber
                    notifications on publish.
            Response: Updated post data, parsed by _digest_result().

        Args:
            post_guid (str): The unique identifier (GUID) of the post
                to publish or unpublish.
            should_notify (bool or str): Whether to send notification
                emails to blog subscribers upon publishing. Mapped to
                'sendNotifications' in the API payload.
            publish_time (str, optional): ISO 8601 timestamp for
                scheduled publishing. None for immediate publish.
                Defaults to None.
            is_draft (str, optional): Draft state flag. Set to 'false'
                to publish, 'true' to unpublish. Defaults to 'false'
                (publish the post).
            **options: Additional keyword arguments passed through to
                BaseClient._call().

        Returns:
            dict or str: The API response, parsed as a dict if the
                response body is valid JSON, otherwise the raw
                response body string.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        post = json.dumps(dict(
            published = publish_time, 
            draft = is_draft, 
            sendNotifications = should_notify))
        raw_response = self._call('posts/%s.json' % post_guid, data=post, method='PUT', content_type='application/json', raw_output=True, **options)
        return raw_response
    
    def create_comment(self, post_guid, author_name, author_email, author_uri, content, **options):
        """Create a new comment on a blog post.

        Serialize comment data as a JSON payload using HubSpot's
        anonymous commenter field naming convention (anonyName,
        anonyEmail, anonyUrl) and send it via POST to the post's
        comments endpoint.

        The JSON payload maps Python parameter names to HubSpot's
        expected field names:
            - author_name -> anonyName
            - author_email -> anonyEmail
            - author_uri -> anonyUrl
            - content -> comment

        Endpoint Access:
            HTTP Method: POST
            URL: /blog/v1/posts/{post_guid}/comments.json
            Auth: API key or OAuth access_token via BaseClient.
            Body: JSON-encoded dict with keys: anonyName,
                anonyEmail, anonyUrl, comment.
            Response: Created comment data, parsed by
                _digest_result().

        Args:
            post_guid (str): The unique identifier (GUID) of the blog
                post to comment on.
            author_name (str): Display name of the comment author,
                mapped to 'anonyName' in the API payload.
            author_email (str): Email address of the comment author,
                mapped to 'anonyEmail' in the API payload.
            author_uri (str): URI or website of the comment author,
                mapped to 'anonyUrl' in the API payload.
            content (str): The comment body text, mapped to 'comment'
                in the API payload.
            **options: Additional keyword arguments passed through to
                BaseClient._call().

        Returns:
            dict or str: The API response, parsed as a dict if the
                response body is valid JSON, otherwise the raw
                response body string.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        post = json.dumps(dict(
            anonyName = author_name, 
            anonyEmail = author_email, 
            anonyUrl = author_uri, 
            comment = content))
        raw_response = self._call('posts/%s/comments.json' % post_guid, data=post, method='POST', content_type='application/json', raw_output=True, **options)
        return raw_response
