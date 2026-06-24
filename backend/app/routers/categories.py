"""Category-Router: flache Liste + CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Category
from app.schemas import CategoryCreate, CategoryRead, CategoryUpdate

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
def list_categories(db: Session = Depends(get_db)) -> list[CategoryRead]:
    rows = db.execute(
        select(Category).order_by(Category.sort_order, Category.name)
    ).scalars().all()
    return [CategoryRead.model_validate(c) for c in rows]


@router.post("", response_model=CategoryRead, status_code=201)
def create_category(
    payload: CategoryCreate, db: Session = Depends(get_db)
) -> CategoryRead:
    if payload.parent_id is not None:
        if not db.get(Category, payload.parent_id):
            raise HTTPException(
                status_code=400,
                detail=f"Parent-Kategorie {payload.parent_id} existiert nicht.",
            )
    cat = Category(**payload.model_dump())
    db.add(cat)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Kategorie '{payload.name}' existiert bereits.",
        )
    db.refresh(cat)
    return CategoryRead.model_validate(cat)


@router.put("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
) -> CategoryRead:
    cat = db.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden.")

    if payload.parent_id is not None and payload.parent_id == category_id:
        raise HTTPException(
            status_code=400, detail="Kategorie kann nicht ihr eigener Parent sein."
        )
    if payload.parent_id is not None and not db.get(Category, payload.parent_id):
        raise HTTPException(
            status_code=400,
            detail=f"Parent-Kategorie {payload.parent_id} existiert nicht.",
        )

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(cat, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Kategorie '{payload.name}' existiert bereits.",
        )
    db.refresh(cat)
    return CategoryRead.model_validate(cat)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db)) -> Response:
    cat = db.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden.")
    db.delete(cat)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)