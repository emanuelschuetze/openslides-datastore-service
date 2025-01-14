from typing import Dict, List, Protocol

from datastore.shared.di import service_as_singleton, service_interface
from datastore.shared.services import ReadDatabase
from datastore.shared.typing import JSON, Fqid, Model
from datastore.shared.util import (
    META_DELETED,
    BadCodingError,
    ModelDoesNotExist,
    ModelExists,
    ModelNotDeleted,
)
from datastore.writer.core import (
    BaseRequestEvent,
    RequestCreateEvent,
    RequestDeleteEvent,
    RequestRestoreEvent,
    RequestUpdateEvent,
)

from .db_events import (
    BaseDbEvent,
    DbCreateEvent,
    DbDeleteEvent,
    DbDeleteFieldsEvent,
    DbListUpdateEvent,
    DbRestoreEvent,
    DbUpdateEvent,
)


@service_interface
class EventTranslator(Protocol):
    def translate(
        self, request_event: BaseRequestEvent, models: Dict[Fqid, Model]
    ) -> List[BaseDbEvent]:
        """
        Translates request events into db events
        """


@service_as_singleton
class EventTranslatorService:

    read_database: ReadDatabase

    def translate(
        self, request_event: BaseRequestEvent, models: Dict[Fqid, Model]
    ) -> List[BaseDbEvent]:
        if isinstance(request_event, RequestCreateEvent):
            self.assert_model_does_not_exist(request_event.fqid, models)
            return [DbCreateEvent(request_event.fqid, request_event.fields)]

        if isinstance(request_event, RequestUpdateEvent):
            self.assert_model_exists(request_event.fqid, models)
            return self.create_update_events(request_event, models)

        if isinstance(request_event, RequestDeleteEvent):
            self.assert_model_exists(request_event.fqid, models)
            model_fields = list(models[request_event.fqid].keys())
            return [DbDeleteEvent(request_event.fqid, model_fields)]

        if isinstance(request_event, RequestRestoreEvent):
            self.assert_model_is_deleted(request_event.fqid, models)
            model_fields = list(models[request_event.fqid].keys())
            return [DbRestoreEvent(request_event.fqid, model_fields)]

        raise BadCodingError()

    def assert_model_does_not_exist(
        self, fqid: Fqid, models: Dict[Fqid, Model]
    ) -> None:
        if fqid in models:
            raise ModelExists(fqid)

    def assert_model_exists(self, fqid: Fqid, models: Dict[Fqid, Model]) -> None:
        if fqid not in models or models[fqid][META_DELETED] is True:
            raise ModelDoesNotExist(fqid)

    def assert_model_is_deleted(self, fqid: Fqid, models: Dict[Fqid, Model]) -> None:
        if fqid not in models or models[fqid][META_DELETED] is False:
            raise ModelNotDeleted(fqid)

    def create_update_events(
        self, request_update_event: RequestUpdateEvent, models: Dict[Fqid, Model]
    ) -> List[BaseDbEvent]:
        db_events: List[BaseDbEvent] = []
        updated_fields: Dict[str, JSON] = {
            field: value
            for field, value in request_update_event.fields.items()
            if value is not None
        }
        if updated_fields:
            db_events.append(DbUpdateEvent(request_update_event.fqid, updated_fields))

        deleted_fields = [
            field
            for field, value in request_update_event.fields.items()
            if value is None
        ]
        if deleted_fields:
            db_events.append(
                DbDeleteFieldsEvent(request_update_event.fqid, deleted_fields)
            )

        add = request_update_event.list_fields.get("add", {})
        remove = request_update_event.list_fields.get("remove", {})
        if add or remove:
            db_events.append(
                DbListUpdateEvent(
                    request_update_event.fqid,
                    add,
                    remove,
                    models[request_update_event.fqid],
                )
            )

        return db_events
