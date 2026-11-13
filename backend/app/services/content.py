from datetime import date

from sqlmodel import Session, col, func, select

from app.core.errors import not_found
from app.core.pagination import paginate_query
from app.models import Article, Quote, User
from app.schemas import generated as api
from app.services import impact, recipes

FEATURED_RECIPES = 4
FEATURED_ARTICLES = 3


def _article_schema(a: Article) -> api.Article:
    return api.Article.model_validate(a, from_attributes=True)


def list_articles(
    session: Session, topic: str | None, cursor: str | None, limit: int
) -> api.ArticlePage:
    statement = select(Article).order_by(col(Article.published_at).desc(), Article.id)
    if topic:
        statement = statement.where(Article.topic == topic)
    rows, next_cursor = paginate_query(session, statement, cursor, limit)
    return api.ArticlePage(items=[_article_schema(a) for a in rows], next_cursor=next_cursor)


def daily_quote(session: Session, today: date | None = None) -> api.Quote:
    today = today or date.today()
    count = session.exec(select(func.count()).select_from(Quote)).one()
    if count == 0:
        raise not_found("No quotes available.")
    quote = session.exec(select(Quote).order_by(Quote.id).offset(today.toordinal() % count)).first()
    return api.Quote(text=quote.text, author=quote.author, date=today)


def big_picture(session: Session, user: User) -> api.BigPicture:
    total, this_week, share, active = impact.community_stats(session, user)
    articles = session.exec(
        select(Article).order_by(col(Article.published_at).desc()).limit(FEATURED_ARTICLES)
    ).all()
    return api.BigPicture(
        community_total=total,
        community_this_week=this_week,
        user_share_percent=share,
        active_members=active,
        featured_recipes=recipes.most_favorited(session, user, FEATURED_RECIPES),
        featured_articles=[_article_schema(a) for a in articles],
    )
