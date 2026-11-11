"""Authenticated, bounded image uploads stored with the application database."""

import base64
import hashlib
import warnings
from io import BytesIO
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageOps
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from app.platform import service
from app.platform.auth import current_user, require_role, store_for
from app.platform.store import now, records

router = APIRouter(prefix="/api/v1", tags=["images and evidence"])


def normalize(raw):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if (
                    image.format not in {"PNG", "JPEG", "WEBP"}
                    or image.width * image.height > 16_000_000
                ):
                    raise ValueError("Use PNG, JPEG or WebP up to 16 megapixels")
                image.verify()
            with Image.open(BytesIO(raw)) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail((2048, 2048))
                image = image.convert("RGB")
                output = BytesIO()
                image.save(output, format="JPEG", quality=90)
                return output.getvalue()
    except Exception as error:
        raise HTTPException(
            422, "Upload a valid PNG, JPEG or WebP image, up to 16 megapixels"
        ) from error


async def store_image(file, user, store, *, product_id=None, order_id=None):
    require_role(user, "SELLER" if product_id else "DRIVER")
    raw = await file.read(2_097_153)
    if not raw or len(raw) > 2_097_152:
        raise HTTPException(413, "Images must be nonempty and at most 2 MB")
    content = await run_in_threadpool(normalize, raw)
    with store.transaction() as tx:
        if product_id:
            require_role(user, "SELLER")
            product = service.must(tx, "products", product_id)
            if product["seller_id"] != user["id"]:
                raise HTTPException(403, "This product belongs to another supplier")
        else:
            require_role(user, "DRIVER")
            order = service.must(tx, "orders", order_id)
            pool = service.must(tx, "pools", order["pool_id"])
            if (
                pool.get("driver_id") != user["id"]
                or order["status"] != "FULFILLING"
                or order.get("pod")
            ):
                raise HTTPException(
                    409, "Upload evidence only for your assigned, open delivery"
                )
        count = tx.connection.execute(
            select(func.count())
            .select_from(records)
            .where(
                records.c.kind == "media",
                records.c.data["owner_id"].as_string() == user["id"],
            )
        ).scalar_one()
        if count >= 100:
            raise HTTPException(
                409, "The account's 100-image storage limit has been reached"
            )
        record = {
            "id": str(uuid4()),
            "owner_id": user["id"],
            "product_id": product_id,
            "order_id": order_id,
            "created_at": now(),
            "content_type": "image/jpeg",
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "data": base64.b64encode(content).decode(),
        }
        tx.put("media", record)
        url = "/api/v1/media/" + record["id"]
        if product_id:
            product["image_url"] = url
            tx.put("products", product)
        tx.audit(
            user["id"],
            "PRODUCT_IMAGE_UPLOADED" if product_id else "DELIVERY_IMAGE_UPLOADED",
            product_id or order_id,
            {"media_id": record["id"]},
        )
        return {
            "id": record["id"],
            "url": url,
            "content_type": record["content_type"],
            "source_sha256": record["source_sha256"],
        }


def validate_image_reference(tx, url, product_id):
    if url.startswith("/api/v1/media/"):
        image = tx.get("media", url.rsplit("/", 1)[-1])
        if not image or image.get("product_id") != product_id:
            raise HTTPException(422, "An uploaded image must belong to this product")


@router.post("/seller/products/{product_id}/image")
async def product_image(
    product_id: str,
    file: UploadFile = File(...),
    user=Depends(current_user),
    store=Depends(store_for),
):
    return await store_image(file, user, store, product_id=product_id)


@router.post("/orders/{order_id}/evidence-image")
async def evidence_image(
    order_id: str,
    file: UploadFile = File(...),
    user=Depends(current_user),
    store=Depends(store_for),
):
    return await store_image(file, user, store, order_id=order_id)


@router.get("/media/{media_id}", response_class=Response, responses={200: {"content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}}})
def read_image(media_id: str, user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        media = service.must(tx, "media", media_id)
        if media.get("order_id"):
            service.order_access(
                tx, user, service.must(tx, "orders", media["order_id"])
            )
        elif "ADMIN" not in user["roles"] and media["owner_id"] != user["id"]:
            from app.platform.router import projection

            if media["product_id"] not in {
                p["id"] for p in projection(tx, user, "unavailable")["products"]
            }:
                raise HTTPException(
                    403, "This image is outside your accessible catalog"
                )
        return Response(
            base64.b64decode(media["data"]),
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; sandbox",
                "Content-Disposition": f'inline; filename="paypool-{media_id}.jpg"',
            },
        )
