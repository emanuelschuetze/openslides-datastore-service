import json

from datastore.reader.flask_frontend.routes import Route
from datastore.shared.di import injector
from datastore.shared.services import EnvironmentService
from datastore.shared.services.environment_service import (
    DATASTORE_DEV_MODE_ENVIRONMENT_VAR,
)
from datastore.shared.util import DeletedModelsBehaviour, id_from_fqid
from tests.util import assert_response_code, assert_success_response


data = {
    "a/1": {
        "field_4": "data",
        "field_5": 42,
        "field_6": [1, 2, 3],
        "meta_position": 2,
    },
    "a/2": {
        "field_4": "data",
        "field_5": 42,
        "field_6": [1, 2, 3],
        "meta_position": 2,
    },
    "b/1": {
        "field_4": "data",
        "field_5": 42,
        "field_6": [1, 2, 3],
        "meta_position": 3,
    },
}


def setup_data(connection, cursor):
    # a/2 is deleted
    for fqid, model in data.items():
        cursor.execute(
            "insert into models (fqid, data, deleted) values (%s, %s, %s)",
            [fqid, json.dumps(model), fqid == "a/2"],
        )
    connection.commit()


def get_data_with_id(fqid):
    model = data[fqid]
    model["id"] = id_from_fqid(fqid)
    return model


def test_simple(json_client, db_connection, db_cur):
    setup_data(db_connection, db_cur)
    response = json_client.post(Route.GET_EVERYTHING.URL, {})
    assert_success_response(response)
    assert response.json == {
        "a": {"1": get_data_with_id("a/1")},
        "b": {"1": get_data_with_id("b/1")},
    }


def test_only_deleted(json_client, db_connection, db_cur):
    setup_data(db_connection, db_cur)
    response = json_client.post(
        Route.GET_EVERYTHING.URL,
        {"get_deleted_models": DeletedModelsBehaviour.ONLY_DELETED},
    )
    assert_success_response(response)
    assert response.json == {"a": {"2": get_data_with_id("a/2")}}


def test_deleted_all_models(json_client, db_connection, db_cur):
    setup_data(db_connection, db_cur)
    response = json_client.post(
        Route.GET_EVERYTHING.URL,
        {"get_deleted_models": DeletedModelsBehaviour.ALL_MODELS},
    )
    assert_success_response(response)
    assert response.json == {
        "a": {"1": get_data_with_id("a/1"), "2": get_data_with_id("a/2")},
        "b": {"1": get_data_with_id("b/1")},
    }


def test_not_found_in_non_dev(json_client):
    injector.get(EnvironmentService).set(DATASTORE_DEV_MODE_ENVIRONMENT_VAR, "0")
    response = json_client.post(Route.GET_EVERYTHING.URL, {})
    assert_response_code(response, 404)
