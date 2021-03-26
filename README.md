# Blog Demo

In this repository, you will find a demo GraphQL Blog application.
With the application, you may create posts, add comments to posts,
and add reactions to comments using GraphQL mutations.

All posts, comments and reactions may be retrieved using GraphQL
queries.

The application is built to run on asynchronous Python 3.9, using a 
Code-first approach to declaring GraphQL schemas 
(see https://github.com/strawberry-graphql/strawberry).

Authentication is handled using **Auth0**, and users are logged in 
using a passwordless email link. 

## Requirements

Before getting the application up and running, the following requirements
need to be met. A `Dockerfile` is provided which will bundle all
requirements and provide an image with a ready-to-launch app.

### Operating System

Tested on Ubuntu 20.04. Other OSes will probably work. One important
requirement for Linux systems, is that `libffi-dev` needs to be installed
before attempting to build the dependencies. On Ubuntu, this is installed
with `apt install libffi-dev`. 

(If you are running through pyenv, you will 
need to rebuild the Python installation after installing `libffi-dev`. This
can be done with: `pyenv install 3.9.2`.)

### Python

Python 3.9 (latest stable) is required; earlier versions of Python will not 
work with this application. That's because it makes use of newer, more
user-friendly APIs for asyncio. 

If you do not wish to upgrade your system Python to this version, you may
either use #pyenv/pyenv, or simply the included Dockerfile.

### Database

The app is designed to work with MySQL 5.6 and later. Other DMBSs will not
work without some code changes.

### External APIs

The application does not handle authentication on its own, but rather
delegates that task to an Auth0 adapter which uses the Auth0 Authentication
and Management APIs. This means that in order to use the application, you will 
need an Auth0 account, along with client credentials and a Management API token.

Use of the app without an Auth0 account is possible, however it requires writing
an adapter for your preferred authentication provision (documentation coming
soon).

## Running the application

Running the application will require completing the following steps:

1. Install the dependencies (not necessary if you will use the docker image)
2. Setup Auth0 App
3. Setup MySQL database
3. Writing the configuration file
4. Starting the application

### Installing dependencies

(Note: If you plan to run under Docker, you may skip this step.)

To install the application dependencies, run the following code for the
application root folder:

```
python -m pip install -U pip poetry
poetry install
```

Note that these instructions will isolate dependencies within a virtualenv,
so there is no need to do this yourself beforehand.

### Setting up an Auth0 app

1. Go to https://auth0.com/ and create an account if you don't have one already.
2. From the dashboard, create a new [Regular Web Application](https://auth0.com/docs/applications/set-up-an-application/register-regular-web-applications). Make note of your app *domain*, *client id* and *client secret*.
3. While in the dashboard, you will need to enable the `email` Passwordless connection, using [this guide](https://auth0.com/docs/connections/passwordless/guides/email-otp) as help. When done, enable the `email` connection from the connections tab on the Application's dashboard.
4. Next, [create and authorize a Machine to Machine application](https://auth0.com/docs/tokens/management-api-access-tokens/create-and-authorize-a-machine-to-machine-application) for the Management API, and [get a Management API token](https://auth0.com/docs/tokens/management-api-access-tokens/get-management-api-access-tokens-for-testing). Make a note of it. (Note: A current shortcoming is that the app can only be used with temporary tokens, causing requests to fail after the token expires.)

### Setting up MySQL database

A standard MySQL database setup will work with this application. Start the server on a host/port
that the environment you run the application in can access, and reate an empty database 
and a user which has full privileges on the database. Make a note of your database name, user
and password.

If you plan to run under Docker, the supplied `docker-compose.yml` configuration includes
a MySQL service that is suitable for running locally. This will create a MySQL container with a
pre-configured database and user (blog_app). The data for this container will be persisted
in an anonymous volume.

### Writing the configuration file

Create a file called `blog-app.toml` in the application's root directory. It should have the 
following contents:

```toml
[blog-app.auth]
domain = "<auth0-domain>"
client_id = "<auth0-client-id>"
client_secret = "<auth0-client-secret>"
management_api_token = "<auth0-management-api-token>"

[blog-app.database]
connection_url = "mysql+aiomysql://<mysql-user>:<mysql-password>@<mysql-host>:<mysql-port>/<mysql-database>"
```

Make the following replacements:

| Replacement                    | Description                                                                                    |
|--------------------------------|------------------------------------------------------------------------------------------------|
| `<auth0-domain>`               | The *domain* from your Auth0 Regular Web Application                                           |
| `<auth0-client-id>`            | Likewise, *client id*                                                                          |
| `<auth0-client-secret>`        | ... the *client secret*                                                                        |
| `<auth0-management-api-token>` | The temporary management API token that you generated                                          |
| `<mysql-host>`                 | The hostname or ip address from which your MySQL instance can be reached                       |
| `<mysql-port>`                 | The port number that MySQL listens on                                                          |
| `<mysql-database>`             | The name of the database that you created for this application, hosted with the MySQL instance |
| `<mysql-user>`                 | The user which has full access to the above database                                           |
| `<mysql-password>`             | The password which authenticates the above user                                                |

(When running using the pre-configured `docker-compose.yml` configuration, the `<mysql-host>` would be `mysql`. The remaining
`<mysql-*>` fields should be copied from the docker-compose configuration.)


### Starting the application

Before running for the first time, you must create the database tables used by the application. This can be accomplished with
`poetry run devtools create-model`. If you you prefer docker-compose, the command is 
`docker-compose run --rm blog_app poetry run devtools create-model`.

Once the above is done, you can start the server.

To start the server, run `poetry run devtools server`.

If you prefer docker-compose, use `docker-compose up`. You may also build the image and start the container yourself. In this case, 
when running the container, you must use a volume to link the config file into the container, and set the `BLOG_APP_SETTINGS`
environment variable to the location of this file.

In both cases, the console will show which port the server listens on.

## Usage

The server is a GraphQL server, listening for GraphQL requests at `/graphql`. The local server also has an instance of
GraphiQL tools running at `http://localhost:<port>/graphql`. This can be used to inspect the available queries and mutations.

This section gives a brief overview of how the server is expected to be used.

### Making queries

All queries to the system use the top-level `posts` GraphQL query. It does not require
authentication. The query and the types that it returns are documented on the GraphQL
server, but a summary of queries is shown below:


**Get all post ids and titles**

```graphql
posts {
  allItems {
    id
    title
  }
}
```

```json
{
  "data": {
    "posts": {
      "allItems": [
        {
          "id": 1,
          "title": "..."
        },
        {
          "id": 2,
          "title": "..."
        }
      ]
    }
  }
}
```

**Get specific posts by id**

```graphql
posts {
  byId(ids: [1, 2, 3, 4000]) {
    title
    content
  }
}
```

```json
{
  "data": {
    "posts": {
      "byId": [
        {
          "title": "...",
          "content": "..."
        },
        {
          "title": "...",
          "content": "..."
        },
        null,
        null
      ]
    }
  }
}
```

**Get all comments on a post**
```graphql
posts {
  byId(ids: 15) {
    comments {
      allItems {
        id
        content
      }
    }
  }
}
```

```json
{
  "data": {
    "posts": {
      "byId": [
        {
          "comments": {
            "allItems": []
          }
        }
      ]
    }
  }
}
```

### Authentication 

**All post, comment and reaction mutations require authentication.** Authentication is only supported
using special one-time-use codes which are emailed to the user. Upon authenticating with a code, an
access token is provided which can be supplied as a bearer token when querying the mutations which require authorization.
This can be done by setting the `Authorization Bearer <the access token>` header when making GraphQL
requests that contain such mutations. Note, however, that access tokens have a short time to live,
and need to be periodically refreshed (using the supplied `refreshLogin` mutation)

The following workflow must be used to retrieve (and refresh) access tokens:

1. Use `sendLoginCode` mutation to send a login code to the user's email address.
2. After the user retrieves the login code, use the `loginWithCode` mutation to retrieve an access token, as well as a refresh token that can be used to get a new access token.
3. When the access token expires, use the `refreshLogin` mutation with the last refresh token to get a new access token and refresh token.


### Authorization

All post, comment and reaction mutations follow a simple authorization model:

- New items may be created by any authenticated user.
- Existing items may only be updated by the user who created them.
- Items may only be removed by the user who created them.

