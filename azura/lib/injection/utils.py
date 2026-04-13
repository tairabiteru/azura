import lightbulb
import linkd


def split_exc(
    exc: lightbulb.exceptions.ExecutionPipelineFailedException
) -> tuple[lightbulb.Context, BaseException | None]:
    if not isinstance(exc.causes[0], linkd.DependencyNotSatisfiableException):
        return exc.context, None
    
    uexc = exc.causes[0]
    if uexc.__cause__ is None:
        return exc.context, None 
    return exc.context, uexc.__cause__.__cause__
    
    