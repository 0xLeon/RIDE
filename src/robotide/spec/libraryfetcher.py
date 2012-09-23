#  Copyright 2008-2012 Nokia Siemens Networks Oyj
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
from Queue import Empty
from multiprocessing import Queue
from multiprocessing.process import Process
import sys
from threading import Thread, Lock
import time
from robot.running import TestLibrary
from robotide.spec.iteminfo import LibraryKeywordInfo
from robotide.spec.librarydatabase import LibraryDatabase, DATABASE_FILE

DB_LOCK = Lock()

def import_library(path, args, library_needs_refresh_listener):
    db = LibraryDatabase(DATABASE_FILE)
    try:
        last_updated = db.get_library_last_updated(path, args)
        if last_updated:
            if time.time() - last_updated > 10.0:
                _refresh_library(path, args, library_needs_refresh_listener)
            return db.fetch_library_keywords(path, args)
        return _get_import_result_from_process_to_db(path, args)
    finally:
        db.close()

def _refresh_library(path, args, library_needs_refresh_listener):
    # Eventually consistent trick
    def execute():
        try:
            _get_import_result_from_process_and_update_db(path, args, library_needs_refresh_listener)
        except ImportError:
            pass
    t = Thread(target=execute)
    t.setDaemon(True)
    t.start()

def _get_import_result_from_process_and_update_db(path, args, library_needs_refresh_listener):
    keywords = _get_import_result_from_process(path, args)
    db = LibraryDatabase(DATABASE_FILE)
    try:
        if _keywords_differ(keywords, db.fetch_library_keywords(path, args)):
            with DB_LOCK:
                db.insert_library_keywords(path, args, keywords)
            library_needs_refresh_listener()
        else:
            with DB_LOCK:
                db.update_library_timestamp_to_current(path, args)
        return keywords
    finally:
        db.close()

def _get_import_result_from_process_to_db(path, args):
    keywords = _get_import_result_from_process(path, args)
    def execute():
        database = LibraryDatabase(DATABASE_FILE)
        try:
            with DB_LOCK:
                database.insert_library_keywords(path, args, keywords)
            return keywords
        finally:
            database.close()
    t = Thread(target=execute)
    t.setDaemon(True)
    t.start()
    return keywords

def _get_import_result_from_process(path, args):
    q = Queue(maxsize=1)
    p = Process(target=_library_initializer, args=(q, path, args))
    p.start()
    while True:
        try:
            result = q.get(timeout=0.1)
            if isinstance(result, Exception):
                raise ImportError(result)
            return result
        except Empty:
            if not p.is_alive():
                raise ImportError()

def _library_initializer(queue, path, args):
    try:
        queue.put(_get_keywords(path, args))
    except Exception, e:
        queue.put(e)
    finally:
        sys.exit()

def _keywords_differ(keywords1, keywords2):
    if keywords1 != keywords2 and None in (keywords1, keywords2):
        return True
    if len(keywords1) != len(keywords2):
        return True
    for k1, k2 in zip(keywords1, keywords2):
        if k1.name != k2.name:
            return True
        if k1.doc != k2.doc:
            return True
        if k1.arguments != k2.arguments:
            return True
        if k1.source != k2.source:
            return True
    return False

def _get_keywords(path, args):
    lib = TestLibrary(path, args)
    return [
        LibraryKeywordInfo(
            kw.name,
            kw.doc,
            kw.library.name,
            _parse_args(kw.arguments)
        ) for kw in lib.handlers.values()]

def _parse_args(handler_args):
    args = []
    if handler_args.names:
        args.extend(list(handler_args.names))
    if handler_args.defaults:
        for i, value in enumerate(handler_args.defaults):
            index = len(handler_args.names) - len(handler_args.defaults) + i
            args[index] = args[index] + '=' + unicode(value)
    if handler_args.varargs:
        args.append('*%s' % handler_args.varargs)
    return args
