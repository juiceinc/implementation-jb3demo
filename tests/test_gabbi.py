"""A test module to exercise the DataServices API with gabbi
This loads the yaml files in the gabbits directory and runs each
of them as a single ordered test suite.
"""

import os
import json

import requests
from gabbi import driver

TESTS_DIR = 'gabbits'


def load_tests(loader, tests, pattern):
    headers = {'Content-Type': 'application/json'}
    session = requests.session()
    r = session.get('http://0.0.0.0:8000/api/v1/stack/869470f2/filters/', headers=headers, auth=('chris@juice.com', 'cremacuban0!'))
    os.environ['GABBI_AUTH'] = r.request.headers['Authorization']

    """Provide a TestSuite to the discovery process."""
    test_dir = os.path.join(os.path.dirname(__file__), TESTS_DIR)
    return driver.build_tests(test_dir, loader, host='localhost', port=8000)
