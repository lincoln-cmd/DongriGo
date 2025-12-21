# apps/blog/management/commands/import_countries.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Set

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.blog.models import Country


def _norm_alias(s: str) -> str:
    return " ".join((s or "").strip().split())


def _safe_upper(s: Optional[str]) -> str:
    return (s or "").strip().upper()


class Command(BaseCommand):
    help = "Import countries from a GeoJSON that contains ISO_A2/ISO_A3 and English name, with optional Korean name map."

    def add_arguments(self, parser):
        parser.add_argument(
            "--geojson",
            required=True,
            help="Path to GeoJSON (features[].properties should include ISO_A2, ISO_A3, and an English name field like ADMIN or NAME_EN).",
        )
        parser.add_argument(
            "--ko-map",
            default="",
            help="Optional path to JSON mapping ISO_A2 -> Korean name. Example: {\"KR\":\"대한민국\",\"JP\":\"일본\"}",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update existing Country rows when ISO_A3 matches (upsert).",
        )
        parser.add_argument(
            "--slug-mode",
            choices=["keep", "iso2", "slugify_en"],
            default="keep",
            help="How to set slug for newly created rows. keep=never change existing, iso2=new slug=iso_a2 lower, slugify_en=new slug=slugify(english).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would change without writing to DB.",
        )

    def handle(self, *args, **opts):
        geojson_path = Path(opts["geojson"]).resolve()
        ko_map_path = (Path(opts["ko_map"]).resolve() if opts["ko_map"] else None)
        update_existing = bool(opts["update_existing"])
        slug_mode = opts["slug_mode"]
        dry_run = bool(opts["dry_run"])

        if not geojson_path.exists():
            self.stderr.write(self.style.ERROR(f"geojson not found: {geojson_path}"))
            return

        ko_map: Dict[str, Any] = {}
        if ko_map_path:
            if not ko_map_path.exists():
                self.stderr.write(self.style.ERROR(f"ko-map not found: {ko_map_path}"))
                return
            ko_map = json.loads(ko_map_path.read_text(encoding="utf-8"))

        data = json.loads(geojson_path.read_text(encoding="utf-8"))
        features = data.get("features") or []
        if not isinstance(features, list):
            self.stderr.write(self.style.ERROR("Invalid GeoJSON: features is not a list"))
            return

        created = 0
        updated = 0
        skipped = 0

        # slug 충돌 방지용
        existing_slugs: Set[str] = set(Country.objects.values_list("slug", flat=True))

        def choose_english_name(props: Dict[str, Any]) -> str:
            # 데이터셋마다 영어 필드 이름이 달라서 후보를 여러 개 둠
            for k in ("ADMIN", "NAME_EN", "NAME", "name", "SOVEREIGNT", "FORMAL_EN"):
                v = (props.get(k) or "").strip()
                if v:
                    return v
            return ""

        def build_display_name(ko: str, en: str) -> str:
            ko = (ko or "").strip()
            en = (en or "").strip()
            if ko and en:
                return f"{ko}({en})"
            if ko:
                return ko
            return en

        def default_slug(iso_a2: str, en_name: str) -> str:
            if slug_mode == "iso2" and iso_a2:
                base = iso_a2.lower()
            elif slug_mode == "slugify_en":
                base = slugify(en_name) or (iso_a2.lower() if iso_a2 else "")
            else:
                # keep 모드에서는 "새로 생성할 때만" fallback로 iso2를 씀
                base = iso_a2.lower() if iso_a2 else (slugify(en_name) or "")

            if not base:
                base = "country"

            slug = base
            i = 2
            while slug in existing_slugs:
                slug = f"{base}-{i}"
                i += 1
            existing_slugs.add(slug)
            return slug

        @transaction.atomic
        def run():
            nonlocal created, updated, skipped

            for feat in features:
                props = (feat.get("properties") or {})
                if not isinstance(props, dict):
                    skipped += 1
                    continue

                def pick_prop(props, *keys):
                    for k in keys:
                        v = props.get(k)
                        if v is not None and str(v).strip():
                            return str(v).strip()
                    return ""
                
                iso_a2 = _safe_upper(pick_prop(
                    props,
                    "ISO_A2",
                    "ISO3166-1-Alpha-2",
                    "iso_a2",
                ))
                
                iso_a3 = _safe_upper(pick_prop(
                    props,
                    "ISO_A3",
                    "ISO3166-1-Alpha-3",
                    "iso_a3",
                    "ADM0_A3",
                ))
                en = choose_english_name(props)

                if not iso_a3 or not en:
                    skipped += 1
                    continue

                ko = ""
                display_override = ""
                
                ko_val = ko_map.get(iso_a2, "") if iso_a2 else ""
                if isinstance(ko_val, dict):
                    ko = (ko_val.get("ko") or "").strip()
                    display_override = (ko_val.get("display") or "").strip()
                else:
                    ko = str(ko_val or "").strip()
                
                display_name = display_override or build_display_name(ko, en)

                # aliases 기본 구성(대소문자는 globe.js가 정규화하므로 하나만 있어도 됨)
                aliases = set()
                for v in (en, iso_a2, iso_a3, props.get("FORMAL_EN"), props.get("NAME_LONG")):
                    t = _norm_alias(str(v or ""))
                    if t:
                        aliases.add(t)

                # 기존 행 찾기: iso_a3 기준(upsert)
                obj = Country.objects.filter(iso_a3=iso_a3).first()

                if obj:
                    if not update_existing:
                        # update_existing가 아니면 existing는 건드리지 않음
                        skipped += 1
                        continue

                    # slug는 keep 모드에서는 절대 변경하지 않음
                    if slug_mode != "keep" and (not obj.slug):
                        obj.slug = default_slug(iso_a2, en)

                    # 표시 필드 업데이트
                    obj.iso_a2 = iso_a2 or obj.iso_a2
                    obj.name_ko = ko or obj.name_ko
                    obj.name_en = en or obj.name_en

                    # name은 "한글(영문)"을 우선으로 덮어씀(원하면 여기 정책만 바꾸면 됨)
                    obj.name = display_name or obj.name

                    # aliases는 기존 + 신규 합치기
                    old_aliases = {a.strip() for a in (obj.aliases or "").split(",") if a.strip()}
                    merged = sorted(old_aliases.union(aliases))
                    obj.aliases = ", ".join(merged)

                    if not dry_run:
                        obj.save()

                    updated += 1
                    continue

                # 신규 생성
                slug = default_slug(iso_a2, en)
                obj = Country(
                    name=display_name or en,
                    slug=slug,
                    iso_a2=iso_a2 or None,
                    iso_a3=iso_a3,
                    name_ko=ko,
                    name_en=en,
                    aliases=", ".join(sorted(aliases)),
                )

                if not dry_run:
                    obj.save()

                created += 1

        run()

        self.stdout.write(self.style.SUCCESS(
            f"import_countries done. created={created}, updated={updated}, skipped={skipped}, dry_run={dry_run}"
        ))
