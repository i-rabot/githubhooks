# Githubhooks

Runs under Turbogears.

Make sure bare repos are owned by apache:
 * Configure so you can login as apache:
   * `usermod -s /bin/bash apache`
 * as apache:
   * `git clone --bare https://github.com/RetailArchitects/loft.git`
   * add full directory to app.ini

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
