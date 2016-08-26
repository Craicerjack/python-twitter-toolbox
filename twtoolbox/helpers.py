# Twitter Toolbox for Python
# Copyright 2016 Hugo Hromic
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Twitter Toolbox for Python helper functions."""

import logging
import json
from codecs import getreader
from os import path, makedirs
try:
    from configparser import ConfigParser  # pylint: disable=import-error
except ImportError:
    from ConfigParser import ConfigParser  # pylint: disable=import-error
try:
    from itertools import izip_longest as zip_longest  # pylint: disable=no-name-in-module
except ImportError:
    from itertools import zip_longest  # pylint: disable=no-name-in-module
import colorlog
from pkg_resources import resource_stream
from tweepy import TweepError, API, AppAuthHandler, OAuthHandler

# module constants
CONFIG_DEFAULTS = "defaults.cfg"
CONFIG_USER = "~/.twtoolbox.cfg"

def _get_latest_id(filename):
    latest_id = None
    with open(filename) as reader:
        for line in reader:
            obj = json.loads(line)
            if latest_id is None or obj["id"] > latest_id:
                latest_id = obj["id"]
    return latest_id

def init_logger(logger):
    """Initialize a logger object."""
    colored_handler = colorlog.StreamHandler()
    colored_handler.setFormatter(colorlog.ColoredFormatter( \
        "%(green)s%(asctime)s%(reset)s " + \
        "%(blue)s[%(cyan)s%(name)s%(blue)s]%(reset)s " + \
        "%(bold)s%(levelname)s%(reset)s " + \
        "%(message)s"))
    logger.setLevel(logging.INFO)
    logger.addHandler(colored_handler)

def read_config():
    """Read default config and overlay user-defined config."""
    config = ConfigParser()
    config.readfp(getreader('ascii')(resource_stream(__name__, CONFIG_DEFAULTS)))  # pylint: disable=deprecated-method
    config.read(path.expanduser(CONFIG_USER))
    return config

def get_app_auth_api(config):
    """Get a Tweepy API object configured using Application-wide Auth."""
    auth = AppAuthHandler(
        config.get("twitter", "consumer_key"),
        config.get("twitter", "consumer_secret"))
    return API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

def get_oauth_api(config):
    """Get a Tweepy API object configured using OAuth."""
    auth = OAuthHandler(
        config.get("twitter", "consumer_key"),
        config.get("twitter", "consumer_secret"))
    auth.set_access_token(
        config.get("twitter", "access_token_key"),
        config.get("twitter", "access_token_secret"))
    return API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

def ensure_at_least_one(user_ids, screen_names):
    """Make sure at least one of user_ids or screen_names has data."""
    if user_ids is None:
        user_ids = []
    if screen_names is None:
        screen_names = []
    if not user_ids and not screen_names:
        raise ValueError("at least user_ids or screen_names must be provided")
    return user_ids, screen_names

def ensure_only_one(user_id, screen_name):
    """Make sure only one of user_id or screen_name has data."""
    if (user_id is None and screen_name is None) or \
        (user_id is not None and screen_name is not None):
        raise ValueError("only user_id or screen_name must be provided")
    return user_id, screen_name

def gen_chunks(*iterables, **kwargs):
    """Generate sequential components chunks of certain size from n-iterables."""
    size = kwargs.get("size", 10)
    merged = [(idx, el) for idx, iterable in enumerate(iterables) for el in iterable]
    for chunk in zip_longest(*([iter(merged)] * size)):
        components = [[el[1] for el in chunk if el is not None and
                       el[0] == idx] for idx in range(len(iterables))]
        yield tuple(components)

def bulk_process(logger, output_dir, filename_tmpl, function, func_input, var_arg, resume=False):  # pylint: disable=too-many-arguments
    """Process a function in bulk using an iterable input and a variable argument."""
    if not path.exists(output_dir):
        makedirs(output_dir)
        logger.info("created output directory: %s", output_dir)
    num_processed = 0
    for basename, value in func_input:
        output_filename = path.join(output_dir, filename_tmpl % basename)

        # check if there is a previous processing and skip or resume it
        latest_id = None
        if path.exists(output_filename):
            if not resume:
                logger.warning("skipping existing file: %s", output_filename)
                continue
            latest_id = _get_latest_id(output_filename)

        # process the input element with the provided function
        try:
            logger.info("processing: %s", value)
            args = {var_arg: value}
            if latest_id is not None:
                args.update({"since_id": latest_id})
                logger.info("latest id processed: %d", latest_id)
            with open(output_filename, "a" if resume else "w") as writer:
                function(writer, **args)
            num_processed += 1
        except TweepError:
            logger.exception("exception while using the REST API")
    return num_processed
