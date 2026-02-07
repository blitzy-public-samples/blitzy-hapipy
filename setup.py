#!/usr/bin/env python
"""Setuptools-based package manifest for hapipy v2.10.6.

This module defines the distribution metadata and dependency configuration
for hapipy, a Python wrapper around HubSpot's REST APIs. It is consumed
by ``pip install``, ``python setup.py install``, and package index tooling.

Package Metadata:
    name: hapipy
    version: 2.10.6
    description: A Python wrapper around HubSpot's APIs.
    author: HubSpot Dev Team (devteam+hapi@hubspot.com)
    url: https://github.com/HubSpot/hapipy

Declared Packages:
    hapi — Core client library containing BaseClient, six domain-specific
        API clients (Blog, Broadcast, Forms, Keywords, Leads, Prospects),
        the error hierarchy, and authentication/logging utilities.
    hapi.mixins — Optional mix-in modules providing extended capabilities
        such as parallel HTTP execution via pycurl.

Dependencies (install_requires):
    nose==1.2.1 — Test runner pinned at a specific version.
    unittest2==0.5.1 — Backported unittest enhancements, pinned.
    simplejson>=2.1.2 — JSON serialization library with a minimum
        version floor, used at runtime for API payload encoding.

    Note: nose and unittest2 are test-time dependencies bundled into
    install_requires rather than isolated in a test_requires or
    extras_require section.  See inline rationale below.

Long Description:
    Sourced at install time by reading README.md from the project root,
    providing the package index (PyPI) with the project overview and
    links to documentation.
"""
from setuptools import setup

setup(
    name='hapipy',
    version='2.10.6',
    description="A python wrapper around HubSpot's APIs",
    long_description=open('README.md').read(),
    author='HubSpot Dev Team',
    author_email='devteam+hapi@hubspot.com',
    url='https://github.com/HubSpot/hapipy',
    # Why: [Assumptions Made] — The download_url still references the v2.10.5
    # tarball despite the version field being 2.10.6.  This appears to be a
    # stale reference retained to avoid breaking existing download links and
    # tooling that may have cached or pinned the previous tarball URL.
    download_url='https://github.com/HubSpot/hapipy/tarball/v2.10.5',
    license='LICENSE.txt',
    packages=['hapi', 'hapi.mixins'],
    # Why: [Trade-offs] — nose and unittest2 are test-runner dependencies
    # included in install_requires instead of a separate test_requires or
    # extras_require['test'] block.  This bundles test tooling with every
    # production install for simplicity, ensuring ``python setup.py test``
    # works without an additional install step.  The trade-off is a larger
    # install footprint for consumers who never run the test suite — an
    # accepted compromise given the small size of these packages and the
    # project's internal-facing usage pattern at the time of authoring.
    install_requires=[
        'nose==1.2.1',
        'unittest2==0.5.1',
        'simplejson>=2.1.2'
    ],
)
