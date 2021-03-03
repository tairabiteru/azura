
from libs.core.conf import conf

import os
import json
from marshmallow import Schema, fields, post_load

class FAQSchema(Schema):
    id = fields.Str()
    aliases = fields.List(fields.Str)
    question = fields.Str()
    content = fields.Str()
    image = fields.Str(allow_none=True)

    @post_load
    def make_obj(self, data, **kwargs):
        return FAQ(**data)

class FAQ:
    @classmethod
    def obtainall(cls):
        all = []
        for file in os.listdir(conf.orm.faqDir):
            with open(os.path.join(conf.orm.faqDir, file)) as file:
                all.append(FAQSchema().load(json.load(file)))
        return all

    @classmethod
    def obtain(cls, id):
        for faq in cls.obtainall():
            if faq.id == id.lower() or id.lower() in faq.aliases:
                return faq
        return None

    @classmethod
    def topics(cls):
        return sorted(list([faq.id for faq in cls.obtainall()]))

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.aliases = kwargs['aliases'] if 'aliases' in kwargs else []
        self.question = kwargs['question'] if 'question' in kwargs else ''
        self.content = kwargs['content'] if 'content' in kwargs else ''
        self.image = kwargs['image'] if 'image' in kwargs else None

    def save(self):
        try:
            os.makedirs(conf.orm.faqDir)
        except FileExistsError:
            pass
        with open(os.path.join(conf.orm.faqDir, f"{self.id}.json"), 'w', encoding='utf-8') as file:
            json.dump(FAQSchema().dump(self), file, sort_keys=True, indent=4, separators=(',', ': '))
