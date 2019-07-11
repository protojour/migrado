"""
migrado constants

Copyright © 2019 Protojour AS, licensed under MIT.
See LICENSE.txt for details.
"""

MIGRATION_TEMPLATE = \
'''#!/usr/bin/arangosh --javascript.execute
// migrado migration v0.1

function forward() {
    var db = require("@arangodb").db
    // add your forward migration here
}

function reverse() {
    var db = require("@arangodb").db
    // add your reverse migration here
}

forward() // default action
'''
