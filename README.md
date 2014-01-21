decss-sync
==========

A tornado.py web app for syncing Decss presentations.

## Usage

This is intended to be used as an asynchronous WebSocket server for [Decss](https://github.com/dryan/decss).

For help with running tornado under nginx, see [http://stackoverflow.com/questions/14749655/setting-up-a-tornado-web-service-in-production-with-nginx-reverse-proxy](http://stackoverflow.com/questions/14749655/setting-up-a-tornado-web-service-in-production-with-nginx-reverse-proxy).

## Configuration

The following environment variables are required:

### Twitter login

For the Twitter login to work, [setup a new Twitter app](https://dev.twitter.com/apps/new).

DECSS_SYNC_TWITTER_API_KEY: set this to the Consumer Key from your new app

DECSS_SYNC_TWITTER_API_SECRET: set this to the Consumer Secret from your new app

### Database

A MySQL database is required. The `schema.sql` file will setup the database schema.

DECSS_SYNC_DATABASE_HOST

DECSS_SYNC_DATABASE_NAME

DECSS_SYNC_DATABASE_USER

DECSS_SYNC_DATABASE_PASSWORD

### Secure Cookies

DECSS_SYNC_COOKIE_SECRET: set this to a good psuedo-random string
