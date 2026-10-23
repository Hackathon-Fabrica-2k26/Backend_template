from rest_framework.routers import SimpleRouter

from .views import ItemViewSet

router = SimpleRouter()
router.register("items", ItemViewSet, basename="item")

urlpatterns = router.urls
