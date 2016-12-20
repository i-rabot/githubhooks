import os

this_directory = os.path.abspath(os.path.dirname(__file__))
default_ini='development.ini'

from paste.deploy import loadapp
# the global_conf is a way to change the cache_dir for apache
application = loadapp('config:' + this_directory + '/' + default_ini, 
    global_conf={'get cache_dir':'apache_cache_dir'})
