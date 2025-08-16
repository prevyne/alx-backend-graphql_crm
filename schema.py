import graphene
import crm.schema

#Inherit from the apps's Query class
class Query(crm.schema.Query, graphene.ObjectType):
    pass

schema = graphene.Schema(query=Query)