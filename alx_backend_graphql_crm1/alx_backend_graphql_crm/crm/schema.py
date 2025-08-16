import graphene

class Query(graphene.ObjectType):
    """
    Defines the root query fields for the CRM API
    """
    hello = graphene.String(default_value="Hello")