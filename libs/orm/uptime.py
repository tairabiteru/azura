from libs.core.conf import conf
from libs.ext.utils import localnow

import datetime
import json
from marshmallow import Schema, fields, post_load
import os

class UptimeRecordSchema(Schema):
    start_timestamp = fields.DateTime()
    end_timestamp = fields.DateTime()

    @post_load
    def make_obj(self, data, **kwargs):
        return UptimeRecord(**data)

class UptimeRecord:
    def __init__(self, **kwargs):
        self.start_timestamp = kwargs['start_timestamp'] if 'start_timestamp' in kwargs else localnow()
        self.end_timestamp = kwargs['end_timestamp'] if 'end_timestamp' in kwargs else self.start_timestamp

    def update(self):
        self.end_timestamp = localnow()
        self.save()

    def commit(self):
        uptime_records = UptimeRecords.obtain()
        uptime_records.all.append(self)
        uptime_records.save()
        try:
            os.remove(os.path.join(conf.orm.botDir, "current_uptime_record.json"))
        except FileNotFoundError:
            pass

    @property
    def elapsed(self):
        return self.end_timestamp - self.start_timestamp

    def save(self):
        try:
            os.makedirs(conf.orm.botDir)
        except FileExistsError:
            pass
        with open(os.path.join(conf.orm.botDir, "current_uptime_record.json"), 'w', encoding='utf-8') as file:
            json.dump(UptimeRecordSchema().dump(self), file, sort_keys=True, indent=4, separators=(',', ': '))

class UptimeRecordsSchema(Schema):
    all = fields.List(fields.Nested(UptimeRecordSchema))

    @post_load
    def make_obj(self, data, **kwargs):
        return UptimeRecords(**data)

class UptimeRecords:
    @classmethod
    def obtain(cls):
        try:
            with open(os.path.join(conf.orm.botDir, "master_uptime_record.json"), 'r', encoding='utf-8') as file:
                return UptimeRecordsSchema().load(json.load(file))
        except FileNotFoundError:
            return cls()

    def __init__(self, **kwargs):
        self.all = kwargs['all'] if 'all' in kwargs else []

    def new_uptime_record(self):
        try:
            self.current_uptime.commit()
        except FileNotFoundError:
            pass
        utr = UptimeRecord()
        utr.save()
        return utr

    def save(self):
        try:
            os.makedirs(conf.orm.botDir)
        except FileExistsError:
            pass
        with open(os.path.join(conf.orm.botDir, "master_uptime_record.json"), 'w', encoding='utf-8') as file:
            json.dump(UptimeRecordsSchema().dump(self), file, sort_keys=True, indent=4, separators=(',', ': '))

    @property
    def current_uptime(self):
        with open(os.path.join(conf.orm.botDir, "current_uptime_record.json"), 'r', encoding='utf-8') as file:
            return UptimeRecordSchema().load(json.load(file))

    @property
    def total_uptime(self):
        uptime = 0
        for record in self.all:
            uptime += record.elapsed.total_seconds()
        uptime += self.current_uptime.elapsed.total_seconds()
        return datetime.timedelta(seconds=uptime)

    @property
    def total_downtime(self):
        downtime = 0
        last = self.all[0]
        for i in range(1, len(self.all)):
            downtime += (self.all[i].start_timestamp - last.end_timestamp).total_seconds()
            last = self.all[i]
        downtime += (self.current_uptime.start_timestamp - self.all[-1].end_timestamp).total_seconds()
        return datetime.timedelta(seconds=downtime)

    @property
    def percentage_up(self):
        return (self.total_uptime.total_seconds() / (self.current_uptime.end_timestamp - self.all[0].start_timestamp).total_seconds()) * 100

    @property
    def percentage_down(self):
        return (self.total_downtime.total_seconds() / (self.current_uptime.end_timestamp - self.all[0].start_timestamp).total_seconds()) * 100
