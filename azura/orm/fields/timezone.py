import pytz
import tortoise


class TimezoneValidator(tortoise.validators.Validator):
    def __call__(self, value):
        try:
            pytz.timezone(value)
        except pytz.exceptions.UnknownTimeZoneError:
            raise tortoise.exceptions.ValidationError(f"The value {value} is not a valid timezone.")


class TimezoneField(tortoise.fields.CharField):
    def __init__(self, **kwargs):
        kwargs['validators'] = [TimezoneValidator()]
        super().__init__(50, **kwargs)

    def to_db_value(self, value, instance):
        if isinstance(value, str):
            self.validate(value)
            value = pytz.timezone(value)
        return value.zone

    def to_python_value(self, value):
        return pytz.timezone(value)
