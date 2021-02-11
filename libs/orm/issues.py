from libs.core.conf import conf
from libs.ext.utils import localnow

import os
import json
from marshmallow import Schema, fields, post_load

class IssueResponseSchema(Schema):
    timestamp = fields.DateTime()
    responder = fields.Int()
    response = fields.Str()

    @post_load
    def make_obj(self, data, **kwargs):
        return IssueResponse(**data)

class IssueResponse:
    def __init__(self, **kwargs):
        self.timestamp = kwargs['timestamp']
        self.responder = kwargs['responder']
        self.response = kwargs['response']

    def render(self, guild):
        name = guild.get_member(self.responder).name if guild.get_member(self.responder) else "Unknown"
        return ("[" + name + "]" + self.timestamp.strftime("[%m/%d/%Y-%H:%M:%S]: "), self.response)


class IssueSchema(Schema):
    id = fields.Int(required=True)
    date = fields.DateTime(required=True)
    title = fields.Str(required=True)
    status_tags = fields.List(fields.Str)
    description = fields.Str()
    responses = fields.List(fields.Nested(IssueResponseSchema))

    @post_load
    def make_obj(self, data, **kwargs):
        return Issue(**data)

class Issue:
    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.date = kwargs['date']
        self.title = kwargs['title']
        self.status_tags = kwargs['status_tags'] if 'status_tags' in kwargs else ['#open']
        self.description = kwargs['description'] if 'description' in kwargs else "No description provided."
        self.description = "No description provided." if self.description == "" else self.description
        self.responses = kwargs['responses'] if 'responses' in kwargs else []

        for tag in self.status_tags:
            if tag.replace("#", "") not in conf.issues.validTags:
                raise ValueError("ID: " + str(self.id) + " Tag: '" + tag + "' is not a valid status tag defined in the constants." )

    @property
    def rendered_tags(self):
        return ", ".join(list(["`" + tag + "`" for tag in self.status_tags]))

    def add_response(self, author=None, response=None):
        self.responses.append(IssueResponse(timestamp=localnow(), responder=author, response=response))

class IssuesSchema(Schema):
    issues = fields.Dict(keys=fields.Int, values=fields.Nested(IssueSchema))

    @post_load
    def make_obj(self, data, **kwargs):
        return Issues(**data)

class Issues:
    @classmethod
    def obtain(cls, id=None, tag=None):
        try:
            with open(os.path.join(conf.orm.botDir, "issues.json"), 'r', encoding='utf-8') as file:
                if id:
                    return IssuesSchema().load(json.load(file)).issues[id]
                elif tag:
                    tag = tag if tag.startswith("#") else "#" + tag
                    matches = {}
                    for id, issue in IssuesSchema().load(json.load(file)).issues.items():
                        if tag in issue.status_tags:
                            matches[str(id)] = issue
                    return matches
                else:
                    return IssuesSchema().load(json.load(file))
        except FileNotFoundError:
            return cls()

    def __init__(self, **kwargs):
        self.issues = kwargs['issues'] if 'issues' in kwargs else {}

    @property
    def last(self):
        try:
            return self.issues[len(self.issues)]
        except KeyError:
            date = localnow()
            return Issue(id=0, date=date, title="none")

    def open(self, title, description="No description provided."):
        issue = Issue(id=self.last.id + 1, title=title, date=localnow(), description=description)
        self.issues[str(issue.id)] = issue
        self.save()
        return issue

    def save(self):
        try:
            os.makedirs(conf.orm.rootDir)
        except FileExistsError:
            pass
        with open(os.path.join(conf.orm.rootDir, "issues.json"), 'w', encoding='utf-8') as file:
            json.dump(IssuesSchema().dump(self), file, sort_keys=True, indent=4, separators=(',', ': '))
