# -*- coding: utf-8 -*-
"""WebHooks controller module"""
from githubhooks.lib.base import BaseController

from tg import expose, request
# from tg.i18n import ugettext as _
# from tg import predicates

import logging
log = logging.getLogger(__name__)

class WebHooksController(BaseController):

    # Uncomment this line if your controller requires an authenticated user
    # allow_only = predicates.not_anonymous()
    
    @expose()
    def simple(self, **kw):
        log.warn("%r" % kw)
        
        log.warn("%r" % request.environ.keys())
        log.warn("%r" % request.params.keys())
        return "OK"
