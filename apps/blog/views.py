from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import BlogCategory, BlogPost


def post_list(request, category_slug=None):
    posts = BlogPost.objects.published().select_related("category", "author")
    category = None
    if category_slug:
        category = get_object_or_404(BlogCategory, slug=category_slug)
        posts = posts.filter(category=category)
    q = request.GET.get("q", "").strip()[:100]
    if q:
        posts = posts.filter(Q(title__icontains=q) | Q(excerpt__icontains=q) | Q(body__icontains=q))
    page = Paginator(posts, 9).get_page(request.GET.get("page"))
    featured = None
    if not q and not category and page.number == 1:
        featured = BlogPost.objects.published().filter(is_featured=True).first()
    return render(request, "blog/list.html", {
        "page_obj": page,
        "posts": page.object_list,
        "category": category,
        "categories": BlogCategory.objects.all(),
        "featured": featured,
        "q": q,
        "noindex": bool(q),
    })


def post_detail(request, slug):
    post = get_object_or_404(BlogPost.objects.select_related("category", "author").prefetch_related("tags"), slug=slug)
    preview = not post.is_live
    if preview and not (request.user.is_authenticated and request.user.has_perm("blog.view_blogpost")):
        raise Http404
    related = list(post.related_posts.published()[:3])
    if len(related) < 3 and post.category_id:
        extra = BlogPost.objects.published().filter(category=post.category).exclude(pk=post.pk).exclude(
            pk__in=[r.pk for r in related])[: 3 - len(related)]
        related += list(extra)
    return render(request, "blog/detail.html", {"post": post, "related": related, "preview": preview, "noindex": preview})
