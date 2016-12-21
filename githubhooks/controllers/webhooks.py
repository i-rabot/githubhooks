# -*- coding: utf-8 -*-
"""WebHooks controller module"""
from githubhooks.lib.base import BaseController
from tg import expose, request, config
from githubhooks.model import git_fetch_lock
import json
import github
import hashlib
import hmac
import re

# from tg.i18n import ugettext as _
# from tg import predicates

import logging
log = logging.getLogger(__name__)


GH_PENDING = 'pending'
GH_SUCCESS = 'success'
GH_ERROR = 'error'
GH_FAILURE = 'failure'


class _InspectionManager(object):
    
    def __init__(self, repo_dict):
        self.hub = github.Github(
            config['githublogin'],
            config['githubpasswd'])
        self.owner = self.hub.get_user(repo_dict['owner']['name'])
        self.repo = self.owner.get_repo(repo_dict['name'])
        if not self.repo:
            raise AssertionError("Couldn't load repo")
    
    def get_commit(self, commitid):
        return self.repo.get_commit(commitid)


class _PushInspector(_InspectionManager):

    CONFLICTS = [
        r'^<<<<<<<($|[^<])',
        r'^=======$',
        r'^>>>>>>>($|[^>])'
    ]
    BREAKPOINT = 'pdb.set_trace'
    
    # git grep -E "(^<<<<<<< HEAD($|[^<])|^=======$|^>>>>>>>($|[^>])|pdb\.set_trace\(\))" 6ffdf6ea0b20822d88e64d4aea4432271d5eb6c1

    def __init__(self, payload):
        log.debug("%r" % payload)
        self.push = json.loads(payload, encoding=request.charset)
        log.info("Processing this push: %s" % self.push['compare'])
        super(_PushInspector, self).__init__(self.push['repository'])
        self.addition_re = re.compile(r"^\+(?P<line>.*)$", re.MULTILINE)
        self.conflict_re = [re.compile(c) for c in self.CONFLICTS]

    def _collect_commits(self):
        commits = []
        for c in self.push['commits']:
            commit = self.get_commit(c['id'])
            # first set them all to pending...
            commit.create_status(GH_PENDING, description='checking commit...')
            commits.append(commit)
        self.commits = commits

    def _process_commit(self, commit):
        errors = []
        for f in commit.files:
            for m in self.addition_re.finditer(f.patch):
                addedline = m.group('line')
                if self.BREAKPOINT in addedline:
                    # We check even for non-python files so engineer
                    # can mark things they don't want committed.
                    errors.append("breakpoint added in %s" % f.filename)
                for marker in self.conflict_re:
                    if marker.match(addedline):
                        errors.append('conflict marker "%s" found in %s' %
                            (addedline, f.filename))
        if errors:
            state = GH_ERROR
            info = "\n".join(errors)
        else:
            state = GH_SUCCESS
            info = "checks passed"
        commit.create_status(state, description=info[:140])

    def inspect(self):
        self._collect_commits()
        for commit in self.commits:
            self._process_commit(commit)


class WebHooksController(BaseController):

    # Uncomment this line if your controller requires an authenticated user
    # allow_only = predicates.not_anonymous()
    
    def validate_signature(self):
        dig = hmac.new(config['webhook_secret'], request.body, hashlib.sha1)
        calculated_sig = "sha1=" + dig.hexdigest()
        if calculated_sig != request.environ['HTTP_X_HUB_SIGNATURE']:
            # not from github or secret is set incorrectly
            raise AssertionError("signature mismatch!")
    
    @expose()
    def inspect_push(self, payload):
        self.validate_signature()
        _PushInspector(payload).inspect()
        return "Finished"
