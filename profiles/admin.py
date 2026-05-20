from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from .models import Profile, Document, KYCVerification, BasicKYCSubmission

admin.site.unregister(User)
admin.site.unregister(Group)

@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    pass

@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass

class BasicKYCSubmissionInline(StackedInline):
    model = BasicKYCSubmission
    can_delete = False
    verbose_name_plural = 'Basic KYC Submission'

class DocumentsInline(StackedInline):
    model = Document
    can_delete = False
    verbose_name_plural = 'KYC Documents'

class KYCVerificationInline(TabularInline):
    model = KYCVerification
    extra = 0
    readonly_fields = ['status', 'admin_notes', 'reviewed_by', 'reviewed_at', 'created_at']
    can_delete = False
    ordering = ['-created_at']

@admin.register(Profile)
class ProfileAdmin(ModelAdmin):
    list_display = ["user", "phone", "kyc_level", "is_complete", "created_at"]
    search_fields = ["user__username", "user__email", "phone"]
    list_filter = ["kyc_level", "is_complete", "created_at"]
    inlines = [BasicKYCSubmissionInline, DocumentsInline, KYCVerificationInline]

@admin.register(BasicKYCSubmission)
class BasicKYCSubmissionAdmin(ModelAdmin):
    list_display = ["profile", "full_name", "created_at"]
    search_fields = ["profile__user__username", "full_name"]

@admin.register(KYCVerification)
class KYCVerificationAdmin(ModelAdmin):
    list_display = ["profile", "status", "reviewed_by", "reviewed_at", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["profile__user__username", "profile__user__email"]
    readonly_fields = [
        "created_at", 
        "updated_at", 
        "id_front_link", 
        "id_back_link", 
        "selfie_link", 
        "proof_link"
    ]
    
    def id_front_link(self, obj):
        doc = getattr(obj.profile, 'documents', None)
        if doc and doc.identification_document_front:
            return format_html('<a href="{}" target="_blank">View Front</a>', doc.identification_document_front.url)
        return "Not Uploaded"
    id_front_link.short_description = "ID Front"

    def id_back_link(self, obj):
        doc = getattr(obj.profile, 'documents', None)
        if doc and doc.identification_document_back:
            return format_html('<a href="{}" target="_blank">View Back</a>', doc.identification_document_back.url)
        return "Not Uploaded"
    id_back_link.short_description = "ID Back"

    def selfie_link(self, obj):
        doc = getattr(obj.profile, 'documents', None)
        if doc and doc.selfie:
            return format_html('<a href="{}" target="_blank">View Selfie</a>', doc.selfie.url)
        return "Not Uploaded"
    selfie_link.short_description = "Selfie"

    def proof_link(self, obj):
        doc = getattr(obj.profile, 'documents', None)
        if doc and doc.proof_of_address:
            return format_html('<a href="{}" target="_blank">View Proof</a>', doc.proof_of_address.url)
        return "Not Uploaded"
    proof_link.short_description = "Proof of Address"

    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status in ['APPROVED', 'REJECTED']:
                obj.reviewed_by = request.user
                obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)

@admin.register(Document)
class DocumentAdmin(ModelAdmin):
    list_display = ["profile", "created_at", "updated_at"]
    search_fields = ["profile__user__username"]
