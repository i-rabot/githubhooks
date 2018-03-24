# -*- coding: utf-8 -*-
"""WebHooks controller module"""
from githubhooks.lib.base import BaseController
from tg import expose, request, config
from githubhooks.model import git_fetch_lock
from subprocess import Popen, PIPE
import json
import github
import hashlib
import hmac
import re
import os

import logging
log = logging.getLogger(__name__)


GH_PENDING = 'pending'
GH_SUCCESS = 'success'
GH_ERROR = 'error'
GH_FAILURE = 'failure'


class _Problem(object):
    
    def __init__(self, rev, filename, lineno, line):
        self.rev = rev
        self.filename = filename
        self.lineno = lineno
        self.line = line
        self.msg = 'Problem'
        
    def __str__(self):
        return "{msg} at {filename},{lineno}: {line}".format(**self.__dict__)


class _InspectionManager(object):
    
    check_name = 'code checks'
    
    def __init__(self, repo_dict):
        self.hub = github.Github(
            config['githublogin'],
            config['githubpasswd'])
        self.owner = self.hub.get_user(repo_dict['owner']['name'])
        self.repo = self.owner.get_repo(repo_dict['name'])
        if not self.repo:
            raise AssertionError("Couldn't load repo")
    
    def update_status(self, commit, state, description):
        commit.create_status(state, 
            description=description, 
            context=self.check_name)
    
    def get_commit(self, commitid, mark_pending=False):
        commit = self.repo.get_commit(commitid)
        if mark_pending:
            self.update_status(commit, GH_PENDING, 'checking commit...')
        return commit

    def git_fetch(self):
        env = os.environ.copy()
        here = os.path.dirname(__file__)
        env['GIT_ASKPASS'] = os.path.abspath("%s/../../gitcreds.sh" % here)
        env['GITUSER'] = config['githublogin']
        env['GITPASS'] = config['githubpasswd']
        std, err, exitcode = self.git_command([
                'fetch',
                'origin',
                '+refs/heads/*:refs/heads/*',
                '--prune'], 
            env)
        if exitcode:
            raise AssertionError("git fetch failed: %s" % err)
        if std:
            log.info("git fetch: %s" % std)
        if err:
            log.info("git fetch: %s" % err)

    def git_file_at(self, filepath, commitid):
        """
        use git show to get the file at specified commit
        """
        # git show 2dfb0399b41e9603215d98cc7579f7eb8d852a39:src/appserver/pylotengine/appsetup/upgrade/dataupdate.py
        std, err, exitcode = self.git_command([
            'show',
            "%s:%s" % (commitid, filepath)])
        if exitcode:
            raise AssertionError("git show failed with %s" % err)
        return std

    def git_command(self, cmd, env=None):
        with git_fetch_lock:
            dir = config['git_%s_directory' % self.repo.name]
            childproc = Popen([
                    config['git_path'], 
                    '--git-dir=%s' % dir,
                ] + cmd, 
                stdout=PIPE, 
                stderr=PIPE, 
                env=env)
            return childproc.communicate() + (childproc.returncode,)


class _PushInspector(_InspectionManager):

    PROBLEMS = [
        (r'^<<<<<<<($|[^<])', 'Conflict start marker'),
        (r'^=======$', 'Conflict marker'),
        (r'^>>>>>>>($|[^>])', 'Conflict end marker'),
        (r'pdb\.set_trace\(\)', 'Breakpoint'),
        (r'\bdebugger\s*;', 'js debugger'),
    ]
    
    def __init__(self, payload):
        log.debug("%r" % payload)
        self.push = json.loads(payload, encoding=request.charset)
        super(_PushInspector, self).__init__(self.push['repository'])
        self._search_regex = None
        self._which_regex = None
        self._update_entry_re = None
        self.uuid_keys = {}

    @property
    def search_regex(self):
        if not self._search_regex:
            self._search_regex = \
                "(%s)" % '|'.join(p[0] for p in self.PROBLEMS)
        return self._search_regex

    @property
    def which_regex(self):
        if not self._which_regex:
            # name each regex i0, i1, i2, etc...
            self._which_regex = re.compile(
                "(?:%s)" % '|'.join('(?P<i%d>%s)' % (i, p[0])
                    for i, p in enumerate(self.PROBLEMS)))
        return self._which_regex

    @property
    def update_entry_re(self):
        if not self._update_entry_re:
            self._update_entry_re = \
                re.compile(r"""^\s*\(\s*(?P<update_key>\S+)\s*,\s*\[\s*$""")
        return self._update_entry_re

    def _git_problem_grep(self, commitid):
        # git grep -n -E "(^<<<<<<< HEAD($|[^<])|^=======$|^>>>>>>>($|[^>])|pdb\.set_trace\(\))" 18788395d36ccb462f0ca49583271a714a0963de
        std, err, exitcode = self.git_command([
            'grep',
            '-n',
            '-I',
            '-E',
            self.search_regex,
            commitid])
        # exitcode 1 with blank err means passed, just no results
        if exitcode > 1 or \
           exitcode and err:
            raise AssertionError("git grep failed with %s" % err)
        # git grep will return ':' delimited
        problems = [_Problem(*p.split(':', 3)) for p in std.splitlines()]
        for p in problems:
            # figure out which re was matched...
            match = self.which_regex.search(p.line)
            # should always have match!
            if match:
                # find index of which re matched 
                # (and get int('2') for 'i2', e.g.), taking first
                i = iter(int(k[1:]) for k, v 
                        in match.groupdict().iteritems() if v).next()
                p.msg = self.PROBLEMS[i][1]
        return [str(p) for p in problems]

    def _find_retailer_rule_files(self, commitid):
        std, err, exitcode = self.git_command([
            'ls-tree',
            '--name-only',
            commitid,
            '--',
            "src/appserver/pylotengine/appsetup/customerdata/"])
        if exitcode:
            raise AssertionError("git ls-tree failed with %s" % err)
        rule_file = re.compile(r"/customerdata/\w{3}.py$")
        return [pth for pth in std.splitlines() if rule_file.search(pth)]

    def _dataupdate_file_problems(self, filename, commitid, token, require):
        problems = []
        updates_re = re.compile(r"^" + token + r"\s*=\s*OrderedDict\(")
        filetext = self.git_file_at(filename, commitid)
        lines = iter(filetext.splitlines())
        for ln in lines:
            if updates_re.match(ln):
                break
        else:
            # Not found
            if require:
                raise AssertionError("Could not find '%s' "
                    "assignment in %s" % (token, filename))
            return problems
        localkeys = set()
        key_re = self.update_entry_re
        # continue with same iterator
        for ln in lines:
            match = key_re.match(ln)
            if match:
                key = match.group('update_key')
                # keys that are svn revisions (integers) can be duplicate, 
                # but not in same file.
                # uuids cannot be duplicated globally
                isuuid = not key.isdigit()
                if isuuid:
                    key = key[1:-1]
                if key in localkeys:
                    problems.append("dataupdate key [%s] duplicated "
                        "in %s" % (key, os.path.basename(filename)))
                elif isuuid and key in self.uuid_keys:
                    problems.append("dataupdate key [%s] is in %s and %s" % (
                        key,
                        os.path.basename(filename),
                        self.uuid_keys[key]))
                # record we've seen this
                localkeys.add(key)
                if isuuid:
                    self.uuid_keys[key] = os.path.basename(filename)
        return problems

    def _dataupdate_problems(self, commitid):
        """
        Make sure dataupdate key isn't a duplicate (copy-paste)
        """
        problems = []
        for retailerfile in self._find_retailer_rule_files(commitid):
            problems.extend(self._dataupdate_file_problems(
                retailerfile, 
                commitid, 
                'updates',
                False))
        problems.extend(self._dataupdate_file_problems(
            'src/appserver/pylotengine/appsetup/upgrade/dataupdate.py', 
            commitid, 
            'UPDATES',
            True))
        return problems

    def process_commit(self, commit):
        log.info("    processing commit %s" % commit.sha)
        errors = self._git_problem_grep(commit.sha)
        if not errors:
            errors.extend(self._dataupdate_problems(commit.sha))
        if errors:
            state = GH_ERROR
            info = "\n".join(errors)
        else:
            state = GH_SUCCESS
            info = "checks passed"
        self.update_status(commit, state, info[:140])
        return not errors

    def _process_other_commits(self):
        # This takes too long in the foreground, GitHub expects this to
        # take place in the background, so just check the head commit...
        return
        
        for c in self.push['commits'][:-1]:
            commit = self.get_commit(c['id'], True)
            self.process_commit(commit)

    def inspect(self):
        log.info("Processing this push: %s" % self.push['compare'])
        self.git_fetch()
        head_commit = self.push['head_commit']
        if head_commit:
            # convert head_commit to pygithub object
            head_commit = self.get_commit(head_commit['id'], True)
            if not self.process_commit(head_commit):
                # If head commit fails, we should check all of them to 
                # indicate where the problem was introduced
                self._process_other_commits()


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
