# Githubhooks

Runs under Turbogears.

Make sure bare repos are owned by apache:
 * Configure so you can login as apache:
   * `usermod -s /bin/bash apache`
 * as apache (for permissions' sake):
   * `git clone --bare https://github.com/RetailArchitects/loft.git`
   * add full path to app.ini
   
For code, see main work engine in `githubhooks/githubhooks/controllers/webhooks.py`

## Default Turbogears instructions:

### Installation and Setup

Install ``githubhooks`` using the setup.py script::

    $ cd githubhooks
    $ python setup.py develop

Create the project database for any model classes defined::

    $ gearbox setup-app

Start the paste http server::

    $ gearbox serve

While developing you may want the server to reload after changes in package files (or its dependencies) are saved. This can be achieved easily by adding the --reload option::

    $ gearbox serve --reload --debug

Then you are ready to go.

Shell::

    $ gearbox tgshell
