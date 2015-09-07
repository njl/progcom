PyCon Program Committee Web App
-------------------------------

The goal of this app is to provide a useful tool for asynchronous review of
PyCon talk submissions. The program committee's job is extensive and daunting,
and I'm trying to knock together a simple web app to allow the work to proceed
as efficiently and effectively as I can. Requiring large groupings of
busy professionals to come together at the same time to chat on IRC is hard,
and doesn't feel very scalable. This is my first step towards understanding how
to scale the whole thing.

Configuring the Applications
------------------------
As currently configured, the application connects to a local postgresql
database in the normal place, with username test and password test.

The application picks up configuration from environment variables. I like to
use the envdir tool, but you can set them however you like. A complete set of
configuration values, reasonable for testing are available in `dev-config/`,
with the exception of `MANDRILL_API_KEY`. You'll have to get your own one of
those.

Running the Application
-----------------
Make a virtualenv, `pip install -r requirements.pip`. Run the application
locally via `envdir dev-config ./app.py`, run the tests via
`envdir dev-config py.test`.

Understanding The Process
------------
The process runs in two rounds; the first is called "kittendome", and is
basically the process of winnowing out talks. Talks which aren't relevant for
PyCon, poorly prepared proposals, or what-have-you, get eliminated from
consideration. Talks aren't compared to one another; a low-ish bar is set, and
talks that don't make it over the bar are removed.

The second part of the process is "thunderdome". In thunderdome, talks are
moved into groups, and those groups are then reviewed one at a time, with
a winner or two picked from every group. Some groups feel weak enough that no
winners are picked.
