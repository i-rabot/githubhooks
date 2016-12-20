import os

DEFAULT_INI = 'development.ini'

this_directory = os.path.abspath(os.path.dirname(__file__))
app_config = this_directory + '/' + DEFAULT_INI

#Setup logging
import logging.config
logging.config.fileConfig(app_config)

from paste.deploy import loadapp
# the global_conf is a way to change the cache_dir for apache
application = loadapp('config:' + app_config, 
    global_conf={'get cache_dir':'apache_cache_dir'})
