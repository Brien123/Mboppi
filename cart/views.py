from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from .models import Cart, CartItem
from products.models import Product
from .serializers import (
    CartSerializer, AddToCartSerializer, UpdateCartItemSerializer,
    CartResponseSerializer
)
from common.serializers import SuccessResponseSerializer

class CartDetailView(generics.GenericAPIView):
    """Retrieve the current user's cart."""
    permission_classes = [IsAuthenticated]
    serializer_class = CartSerializer

    @extend_schema(responses={200: CartResponseSerializer},tags=['Cart'])
    def get(self, request, *args, **kwargs):
        cart, created = Cart.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(cart)
        return Response({
            "message": _("Cart retrieved successfully."),
            "data": serializer.data
        }, status=status.HTTP_200_OK)

class AddToCartView(generics.GenericAPIView):
    """Add a product to the cart."""
    permission_classes = [IsAuthenticated]
    serializer_class = AddToCartSerializer

    @extend_schema(request=AddToCartSerializer,responses={200: CartResponseSerializer},tags=['Cart'])
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_id = serializer.validated_data['product_id']
        quantity = serializer.validated_data['quantity']
        
        cart, created = Cart.objects.get_or_create(user=request.user)
        product = Product.objects.get(id=product_id)
        
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )
        
        if not created:
            cart_item.quantity += quantity
            # Re-validate stock for total quantity
            if cart_item.quantity > product.stock:
                 return Response(SuccessResponseSerializer({
                    "message": _("Not enough stock available for total quantity."),
                    "data": None
                }).data, status=status.HTTP_400_BAD_REQUEST)
            cart_item.save()
            
        return Response({
            "message": _("Product added to cart."),
            "data": CartSerializer(cart, context={'request': request}).data
        }, status=status.HTTP_200_OK)

class UpdateCartItemView(generics.GenericAPIView):
    """Update quantity of an item in the cart."""
    permission_classes = [IsAuthenticated]
    serializer_class = UpdateCartItemSerializer

    @extend_schema(request=UpdateCartItemSerializer,responses={200: CartResponseSerializer},tags=['Cart'])
    def patch(self, request, item_id, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            cart_item = CartItem.objects.get(id=item_id, cart__user=request.user)
        except CartItem.DoesNotExist:
            return Response(SuccessResponseSerializer({
                "message": _("Cart item not found."),
                "data": None
            }).data, status=status.HTTP_404_NOT_FOUND)
            
        quantity = serializer.validated_data['quantity']
        
        if quantity > cart_item.product.stock:
            return Response(SuccessResponseSerializer({
                "message": _("Not enough stock available."),
                "data": None
            }).data, status=status.HTTP_400_BAD_REQUEST)
            
        cart_item.quantity = quantity
        cart_item.save()
        
        return Response({
            "message": _("Cart item updated."),
            "data": CartSerializer(cart_item.cart, context={'request': request}).data
        }, status=status.HTTP_200_OK)

class RemoveCartItemView(APIView):
    """Remove an item from the cart."""
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None,responses={200: CartResponseSerializer},tags=['Cart'])
    def delete(self, request, item_id, *args, **kwargs):
        try:
            cart_item = CartItem.objects.get(id=item_id, cart__user=request.user)
            cart = cart_item.cart
            cart_item.delete()
        except CartItem.DoesNotExist:
            return Response(SuccessResponseSerializer({
                "message": _("Cart item not found."),
                "data": None
            }).data, status=status.HTTP_404_NOT_FOUND)
            
        return Response({
            "message": _("Cart item removed."),
            "data": CartSerializer(cart, context={'request': request}).data
        }, status=status.HTTP_200_OK)

class ClearCartView(APIView):
    """Remove all items from the cart."""
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None,responses={200: CartResponseSerializer},tags=['Cart'])
    def post(self, request, *args, **kwargs):
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart.items.all().delete()
        
        return Response({
            "message": _("Cart cleared."),
            "data": CartSerializer(cart, context={'request': request}).data
        }, status=status.HTTP_200_OK)
