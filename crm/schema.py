import graphene
import re
from django.core.exceptions import ValidationError
from django.db import transaction
from graphene_django import DjangoObjectType
from .models import Customer, Product, Order
from graphene_django.filter import DjangoFilterConnectionField
from .filters import CustomerFilter, ProductFilter, OrderFilter

# 1. GraphQL Types for the Django Models
class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        fields = ("id", "name", "email", "phone", "created_at")

class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        fields = ("id", "name", "description", "price", "stock")

class OrderType(DjangoObjectType):
    class Meta:
        model = Order
        fields = ("id", "customer", "products", "order_date", "total_amount")

# 2. Input Types for Mutations
class CustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String()

# 3. Mutation Classes

# --- Customer Mutations ---
class CreateCustomer(graphene.Mutation):
    class Arguments:
        input = CustomerInput(required=True)

    customer = graphene.Field(CustomerType)
    message = graphene.String()

    @staticmethod
    def mutate(root, info, input):
        # Validate phone format
        phone_pattern = re.compile(r'^\+?1?\d{9,15}$') # Simple phone regex
        if input.phone and not phone_pattern.match(input.phone):
            raise ValidationError("Invalid phone number format. Use formats like +1234567890.")

        # Validate unique email
        if Customer.objects.filter(email=input.email).exists():
            raise ValidationError("A customer with this email already exists.")

        customer = Customer(name=input.name, email=input.email, phone=input.phone)
        customer.save()
        return CreateCustomer(customer=customer, message="Customer created successfully.")

class BulkCreateCustomers(graphene.Mutation):
    class Arguments:
        input = graphene.List(graphene.NonNull(CustomerInput), required=True)

    customers = graphene.List(CustomerType)
    errors = graphene.List(graphene.String)

    @staticmethod
    def mutate(root, info, input):
        successful_customers = []
        error_messages = []
        customers_to_create = []

        for i, customer_data in enumerate(input):
            # Basic validation
            if not customer_data.name or not customer_data.email:
                error_messages.append(f"Record {i+1}: Name and email are required.")
                continue
            if Customer.objects.filter(email=customer_data.email).exists():
                error_messages.append(f"Record {i+1}: Email '{customer_data.email}' already exists.")
                continue

            customers_to_create.append(
                Customer(name=customer_data.name, email=customer_data.email, phone=customer_data.get('phone'))
            )

        # Bulk create valid customers in a single transaction
        if customers_to_create:
            try:
                with transaction.atomic():
                    successful_customers = Customer.objects.bulk_create(customers_to_create)
            except Exception as e:
                error_messages.append(f"Bulk creation failed: {str(e)}")


        return BulkCreateCustomers(customers=successful_customers, errors=error_messages)

# --- Product Mutation ---
class CreateProduct(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        price = graphene.Decimal(required=True)
        stock = graphene.Int()

    product = graphene.Field(ProductType)

    @staticmethod
    def mutate(root, info, name, price, stock=0):
        if price <= 0:
            raise ValidationError("Price must be a positive value.")
        if stock < 0:
            raise ValidationError("Stock cannot be negative.")

        product = Product(name=name, price=price, stock=stock)
        product.save()
        return CreateProduct(product=product)


# --- Order Mutation ---
class CreateOrder(graphene.Mutation):
    class Arguments:
        customer_id = graphene.ID(required=True)
        product_ids = graphene.List(graphene.NonNull(graphene.ID), required=True)
        order_date = graphene.DateTime()

    order = graphene.Field(OrderType)

    @staticmethod
    @transaction.atomic
    def mutate(root, info, customer_id, product_ids, order_date=None):
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            raise ValidationError("Invalid customer ID.")

        if not product_ids:
            raise ValidationError("At least one product must be selected.")

        products = Product.objects.filter(pk__in=product_ids)
        if len(products) != len(product_ids):
            raise ValidationError("One or more product IDs are invalid.")

        total_amount = sum(product.price for product in products)

        order = Order(customer=customer, total_amount=total_amount)
        if order_date:
            order.order_date = order_date
        order.save()

        # ManyToMany relationships must be set after the instance is saved
        order.products.set(products)

        return CreateOrder(order=order)


# 4. Root Mutation Class
class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()


# 5. Root Query Class
class Query(graphene.ObjectType):
    """
    Defines filtered and paginated queries for CRM models.
    """
    hello = graphene.String(default_value="Hello, GraphQL!")

    # A single node field for fetching any object by its global ID
    node = graphene.relay.Node.Field()

    # Use DjangoFilterConnectionField to add filtering and pagination
    all_customers = DjangoFilterConnectionField(CustomerType, filterset_class=CustomerFilter)
    all_products = DjangoFilterConnectionField(ProductType, filterset_class=ProductFilter)
    all_orders = DjangoFilterConnectionField(OrderType, filterset_class=OrderFilter)