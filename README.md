PyCon Program Committee Web App
-------------------------------

The goal of this app is to provide a useful tool for asynchronous review of
PyCon talk submissions. The program committee's job is extensive and daunting,
and I'm trying to knock together a simple web app to allow the work to proceed
as efficiently and effectively as I can. Requiring large groupings of
busy professionals to come together at the same time to chat on IRC is hard,
and doesn't feel very scalable. This is my first step toward understanding how
to scale the whole thing.



Configuring the Applications
------------------------

The application picks up configuration from environment variables. I like to
use the envdir tool, but you can set them however you like. A complete set of
configuration values, reasonable for testing, are available in `dev-config/`.

You can install envdir via `brew install daemontools` on OS X, and `apt-get
install daemontools` on Ubuntu and Debian.

As configured by the values in `dev-config`, the application connects to a local
postgresql database, with username, password, and database name 'test'.

Configuring the Database
---------------------

The application uses a Postgresql database. If you're not familiar with setting
up Postgresql, I've included `setup_db.sql` for you. Getting to the point where
you're able to execute those commands is going to depend on your system. If
you're on a Ubuntu-like system, and you've installed postgresql via something
like `apt-get install postgresql`, you can probably run the `psql` command via
something like `sudo -U postgres psql`. On OSX, if you've installed postgresql
via brew, with something like `brew install postgresql`, you can probably just
type `psql`.

You can create the test database and test user via 
`psql template1 < setup_db.sql`.

The unit tests will create the tables for you, or you can do something like
`psql -U test test < tables.sql` to create empty tables from scratch.




Running the Application
-----------------
Make a virtualenv, `pip install -r requirements.pip`. Run the application
locally via `envdir dev-config ./app.py`, run the tests via
`envdir dev-config py.test`.

You can fill the database up with lots of lorem ipsum nonsense by running the
script `envdir dev-config ./fill_db_with_fakes.py`. You can then log in with
an email from the sequence `user{0-24}@example.com`, and a password of `abc123`.
`user0@example.com` is an administrator.



Deployment
----------

You'll need deploy-config in your root directory, which should have all the
appropriate secrets. From the application's root directory, you can run
`ansible-playbook -i hosts deploy.yaml`.



Understanding The PyCon Talk Review Process
------------
The process runs in two rounds; the first is called "screening", and is
basically about winnowing out talks. Talks which aren't relevant for
PyCon, have poorly prepared proposals, or otherwise won't make the cut, get
eliminated from consideration early. Talks aren't compared to one another; a
low-ish bar is set, and talks that don't make it over the bar are removed.

The second part of the process is "batch". In batch, talks are
moved into groups, and those groups are then reviewed one at a time, with
a winner or two picked from every group. Some groups feel weak enough that no
winners are picked.

To turn on Batch, `echo 1 > dev-config/THIS_IS_BATCH`.
