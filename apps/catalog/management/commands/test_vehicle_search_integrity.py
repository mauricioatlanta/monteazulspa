# -*- coding: utf-8 -*-
"""
Comando de prueba real (sin mocks) para validar el motor de búsqueda por vehículo.

Usa la misma lógica central: build_vehicle_result_context().
Valida: verified, suggested_brand_wide, suggested_other; sin contaminación;
filtro técnico y orden de ranking.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from django.core.management.base import BaseCommand
from django.core.management import call_command

from apps.catalog.models import (
    Product,
    ProductCompatibility,
    VehicleBrand,
    VehicleModel,
    VehicleEngine,
)
from apps.catalog.services.vehicle_search_result_builder import build_vehicle_result_context
from apps.catalog.services.vehicle_technical_profile import (
    build_vehicle_profile,
    product_technical_rank_key,
)


def _product_passes_technical_fit(product: Product, profile: Dict[str, Any]) -> bool:
    """
    Comprueba si un producto cumple las reglas del filtro técnico (combustible, euro, cc).
    Debe coincidir con la lógica de filter_products_by_technical_fit.
    """
    if not profile:
        return True
    fuel_norm = profile.get("fuel_norm")
    if fuel_norm:
        p_fuel = getattr(product, "combustible", None)
        if p_fuel is not None and p_fuel != fuel_norm:
            return False
    euro_norm = profile.get("euro_norm")
    if euro_norm:
        p_euro = getattr(product, "euro_norm", None)
        if p_euro is not None and p_euro != euro_norm:
            return False
    cc = profile.get("displacement_cc")
    if cc is not None and cc > 0:
        lo = getattr(product, "recommended_cc_min", None)
        hi = getattr(product, "recommended_cc_max", None)
        if lo is not None or hi is not None:
            tolerance = 300 if cc < 2000 else 500
            cc_lo = cc - tolerance
            cc_hi = cc + tolerance
            # Rango del producto debe intersectar [cc_lo, cc_hi]
            if lo is None or hi is None:
                return False
            if not (lo <= cc_hi and hi >= cc_lo):
                return False
    return True


def _profile_str(profile: Dict[str, Any]) -> str:
    parts = []
    if profile.get("fuel_norm"):
        parts.append(f"fuel={profile['fuel_norm']}")
    if profile.get("euro_norm"):
        parts.append(f"euro={profile['euro_norm']}")
    if profile.get("displacement_cc") is not None:
        parts.append(f"cc={profile['displacement_cc']}")
    return " ".join(parts) or "—"


class Command(BaseCommand):
    help = (
        "Valida el motor de búsqueda por vehículo (verified, suggested_brand_wide, suggested_other) "
        "contra la base real. Sin mocks."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limita cuántos casos automáticos probar (0 = sin límite).",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Imprime IDs, notas, compatibilidades y rank keys por producto sugerido.",
        )
        parser.add_argument(
            "--sku",
            type=str,
            default="",
            help="Prueba solo casos asociados a este SKU.",
        )
        parser.add_argument(
            "--only-exact",
            action="store_true",
            help="Prueba solo casos con compatibilidad exacta (model != null).",
        )
        parser.add_argument(
            "--only-brand-wide",
            action="store_true",
            help="Prueba solo casos con compatibilidad por marca (model is null).",
        )
        parser.add_argument(
            "--debug-failures",
            action="store_true",
            dest="debug_failures",
            default=False,
            help="En cada caso FAIL, ejecuta el debug detallado (debug_vehicle_search_case).",
        )

    def handle(self, *args, **options) -> None:
        limit = options["limit"] or 0
        verbose = options["verbose"]
        sku_filter = (options["sku"] or "").strip()
        only_exact = options["only_exact"]
        only_brand_wide = options["only_brand_wide"]
        debug_failures = options.get("debug_failures", False)

        if only_exact and only_brand_wide:
            self.stdout.write(self.style.WARNING("--only-exact y --only-brand-wide no pueden usarse juntos."))
            return

        # Construir casos desde ProductCompatibility (base real)
        exact_cases = self._collect_exact_match_cases(sku_filter)
        brand_wide_cases = self._collect_brand_wide_cases(sku_filter)

        cases: List[Tuple[str, Dict[str, Any], Optional[str]]] = []  # (label, case_data, expected_sku)
        if not only_brand_wide:
            for c in exact_cases:
                cases.append((c["label"], c, c["expected_sku"]))
        if not only_exact:
            for c in brand_wide_cases:
                cases.append((c["label"], c, None))  # expected in brand_wide, not verified

        if limit > 0:
            cases = cases[:limit]

        if not cases:
            self.stdout.write("No hay casos que probar (revisa --sku, --only-exact, --only-brand-wide).")
            return

        stats = {
            "total": len(cases),
            "passed": 0,
            "failed": 0,
            "failed_exact_match": 0,
            "failed_brand_wide": 0,
            "failed_duplicate_separation": 0,
            "failed_technical_filter": 0,
            "failed_ranking_order": 0,
        }

        for idx, (label, case_data, expected_verified_sku) in enumerate(cases, 1):
            is_exact_case = expected_verified_sku is not None
            result = self._run_one_case(
                idx=idx,
                label=label,
                case_data=case_data,
                expected_verified_sku=expected_verified_sku,
                is_exact_case=is_exact_case,
                verbose=verbose,
                stats=stats,
                debug_failures=debug_failures,
            )
            if result == "PASS":
                stats["passed"] += 1
            else:
                stats["failed"] += 1
                if debug_failures:
                    self._run_debug_for_failure(case_data, expected_verified_sku, is_exact_case)

        self._print_summary(stats)

    def _collect_exact_match_cases(self, sku_filter: str) -> List[Dict[str, Any]]:
        """Compatibilidades con model no nulo: cada una debe dar verified."""
        qs = (
            ProductCompatibility.objects.filter(
                model__isnull=False,
                is_active=True,
            )
            .select_related("product", "brand", "model", "engine")
            .order_by("product__sku", "brand__name", "model__name")
        )
        if sku_filter:
            qs = qs.filter(product__sku=sku_filter)

        seen = set()
        cases = []
        for compat in qs:
            if not compat.product or not compat.brand or not compat.model:
                continue
            key = (compat.product_id, compat.brand_id, compat.model_id)
            if key in seen:
                continue
            seen.add(key)
            year = compat.year_from
            if compat.year_from != compat.year_to:
                year = (compat.year_from + compat.year_to) // 2
            engine_id = compat.engine_id
            if not engine_id and compat.model_id:
                first_engine = VehicleEngine.objects.filter(model_id=compat.model_id).first()
                if first_engine:
                    engine_id = first_engine.id
            engine_name = ""
            if compat.engine:
                engine_name = f" {compat.engine.name}"
            label = f"{compat.brand.name} {compat.model.name} {year}{engine_name}"
            cases.append({
                "label": label,
                "brand_id": compat.brand_id,
                "model_id": compat.model_id,
                "year": year,
                "engine_id": engine_id,
                "fuel_type": getattr(compat.engine, "fuel_type", None) if compat.engine else compat.fuel_type,
                "displacement_cc": getattr(compat.engine, "displacement_cc", None) if compat.engine else compat.displacement_cc,
                "expected_sku": compat.product.sku,
                "expected_product_id": compat.product_id,
                "compat": compat,
            })
        return cases

    def _collect_brand_wide_cases(self, sku_filter: str) -> List[Dict[str, Any]]:
        """Compatibilidades con model null: producto debe ir a suggested_brand_wide, no verified."""
        qs = (
            ProductCompatibility.objects.filter(
                model__isnull=True,
                is_active=True,
            )
            .select_related("product", "brand")
            .order_by("product__sku", "brand__name")
        )
        if sku_filter:
            qs = qs.filter(product__sku=sku_filter)

        seen = set()
        cases = []
        for compat in qs:
            if not compat.product or not compat.brand:
                continue
            key = (compat.product_id, compat.brand_id)
            if key in seen:
                continue
            seen.add(key)
            year = compat.year_from
            if compat.year_from != compat.year_to:
                year = (compat.year_from + compat.year_to) // 2
            model = VehicleModel.objects.filter(brand_id=compat.brand_id).first()
            if not model:
                continue
            label = f"{compat.brand.name} {model.name} {year} (brand-wide: {compat.product.sku})"
            cases.append({
                "label": label,
                "brand_id": compat.brand_id,
                "model_id": model.id,
                "year": year,
                "engine_id": None,
                "fuel_type": compat.fuel_type,
                "displacement_cc": compat.displacement_cc,
                "expected_sku_brand_wide": compat.product.sku,
                "expected_product_id": compat.product_id,
                "compat": compat,
            })
        return cases

    def _run_one_case(
        self,
        idx: int,
        label: str,
        case_data: Dict[str, Any],
        expected_verified_sku: Optional[str],
        is_exact_case: bool,
        verbose: bool,
        stats: Dict[str, int],
        debug_failures: bool = False,
    ) -> str:
        """Ejecuta la búsqueda real y valida. Retorna 'PASS' o 'FAIL'."""
        ctx = build_vehicle_result_context(
            brand_id=case_data["brand_id"],
            model_id=case_data["model_id"],
            year=case_data["year"],
            engine_id=case_data.get("engine_id"),
            fuel_type=case_data.get("fuel_type"),
            displacement_cc=case_data.get("displacement_cc"),
        )

        if ctx is None:
            self._print_case_header(idx, label, expected_verified_sku, is_exact_case)
            self.stdout.write(self.style.ERROR("RESULT: FAIL"))
            self.stdout.write("REASON: build_vehicle_result_context returned None (brand/model/year inválidos)")
            self._print_sep()
            if is_exact_case:
                stats["failed_exact_match"] += 1
            else:
                stats["failed_brand_wide"] += 1
            return "FAIL"

        profile = ctx["profile"]
        products_verified = list(ctx["products_verified"])
        products_suggested_brand_wide = ctx["products_suggested_brand_wide"]
        products_suggested_other = ctx["products_suggested_other"]

        verified_skus = [p.sku for p in products_verified]
        brand_wide_skus = [p.sku for p in products_suggested_brand_wide]
        other_skus = [p.sku for p in products_suggested_other]

        fail_reasons: List[str] = []
        failed_types_this_case: set = set()

        # A. Exact match: producto esperado debe estar en verified
        if is_exact_case and expected_verified_sku:
            if expected_verified_sku not in verified_skus:
                fail_reasons.append("expected exact-match product was not returned in verified")
                failed_types_this_case.add("exact_match")
            if expected_verified_sku in brand_wide_skus and expected_verified_sku not in verified_skus:
                fail_reasons.append("expected exact-match product appeared only in brand_wide")
                failed_types_this_case.add("exact_match")

        # B. Brand-wide: producto NO en verified, SÍ en suggested_brand_wide
        if not is_exact_case:
            expected_bw = case_data.get("expected_sku_brand_wide")
            if expected_bw:
                if expected_bw in verified_skus:
                    fail_reasons.append("brand-wide product incorrectly appeared in verified")
                    failed_types_this_case.add("brand_wide")
                elif expected_bw not in brand_wide_skus:
                    fail_reasons.append("brand-wide product was not returned in suggested_brand_wide")
                    failed_types_this_case.add("brand_wide")

        # C. No duplicados entre bloques
        verified_ids = {p.id for p in products_verified}
        bw_ids = {p.id for p in products_suggested_brand_wide}
        other_ids = {p.id for p in products_suggested_other}
        if verified_ids & bw_ids or verified_ids & other_ids or bw_ids & other_ids:
            fail_reasons.append("duplicate product_id found across blocks")
            failed_types_this_case.add("duplicate_separation")

        # D. Filtro técnico en suggested
        for p in products_suggested_brand_wide + products_suggested_other:
            if not _product_passes_technical_fit(p, profile):
                fail_reasons.append(f"product {p.sku} in suggested does not pass technical filter")
                failed_types_this_case.add("technical_filter")
                break

        # E. Orden de ranking en suggested_brand_wide y suggested_other
        ranking_ok_brand_wide = True
        ranking_ok_other = True
        for block_name, block in [("BRAND WIDE", products_suggested_brand_wide), ("OTHER", products_suggested_other)]:
            if len(block) < 2:
                continue
            keys = [product_technical_rank_key(p, profile) for p in block]
            for i in range(len(keys) - 1):
                if keys[i] < keys[i + 1]:
                    fail_reasons.append(f"suggested_{block_name.lower().replace(' ', '_')} ranking order violated")
                    failed_types_this_case.add("ranking_order")
                    if block_name == "BRAND WIDE":
                        ranking_ok_brand_wide = False
                    else:
                        ranking_ok_other = False
                    break

        for ft in failed_types_this_case:
            stats[f"failed_{ft}"] += 1

        passed = len(fail_reasons) == 0

        # Salida
        self._print_case_header(idx, label, expected_verified_sku, is_exact_case)
        self.stdout.write(f"PROFILE: {_profile_str(profile)}")
        self.stdout.write(f"VERIFIED: {verified_skus}")
        self.stdout.write(f"BRAND_WIDE: {brand_wide_skus}")
        self.stdout.write(f"OTHER: {other_skus}")

        if verbose:
            self.stdout.write(f"VERIFIED IDs: {[p.id for p in products_verified]}")
            if case_data.get("compat"):
                c = case_data["compat"]
                self.stdout.write(
                    f"COMPAT: product_id={c.product_id} brand_id={c.brand_id} model_id={c.model_id} "
                    f"year_from={c.year_from} year_to={c.year_to} engine_id={c.engine_id}"
                )
            if products_suggested_brand_wide or products_suggested_other:
                self.stdout.write("SUGGESTED BRAND WIDE RANKS:")
                for p in products_suggested_brand_wide:
                    k = product_technical_rank_key(p, profile)
                    self.stdout.write(f"  {p.sku} -> {k}")
                self.stdout.write(f"RANK ORDER: {'PASS' if ranking_ok_brand_wide else 'FAIL'}")
                self.stdout.write("SUGGESTED OTHER RANKS:")
                for p in products_suggested_other:
                    k = product_technical_rank_key(p, profile)
                    self.stdout.write(f"  {p.sku} -> {k}")
                self.stdout.write(f"RANK ORDER: {'PASS' if ranking_ok_other else 'FAIL'}")

        if passed:
            self.stdout.write(self.style.SUCCESS("RESULT: PASS"))
        else:
            self.stdout.write(self.style.ERROR("RESULT: FAIL"))
            for r in fail_reasons:
                self.stdout.write(self.style.ERROR(f"REASON: {r}"))
        self._print_sep()
        return "PASS" if passed else "FAIL"

    def _print_case_header(
        self, idx: int, label: str, expected_verified_sku: Optional[str], is_exact_case: bool
    ) -> None:
        self._print_sep()
        self.stdout.write(f"CASE {idx}: {label}")
        if is_exact_case and expected_verified_sku:
            self.stdout.write(f"EXPECTED VERIFIED: {expected_verified_sku}")
        self._print_sep()

    def _print_sep(self) -> None:
        self.stdout.write("=" * 50)

    def _run_debug_for_failure(
        self,
        case_data: Dict[str, Any],
        expected_verified_sku: Optional[str],
        is_exact_case: bool,
    ) -> None:
        """Ejecuta debug detallado para el caso fallido."""
        sku = expected_verified_sku if is_exact_case else case_data.get("expected_sku_brand_wide")
        if not sku:
            return
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(">>> DEBUG FAILURE >>>"))
        try:
            call_command(
                "debug_vehicle_search_case",
                sku=sku,
                brand_id=case_data.get("brand_id"),
                model_id=case_data.get("model_id"),
                year=case_data.get("year"),
                verbosity=2,
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Debug command error: {e}"))
        self.stdout.write(self.style.WARNING("<<< END DEBUG <<<"))
        self.stdout.write("")

    def _print_summary(self, stats: Dict[str, int]) -> None:
        self.stdout.write("")
        self._print_sep()
        self.stdout.write("RESUMEN FINAL")
        self._print_sep()
        self.stdout.write(f"Total cases: {stats['total']}")
        self.stdout.write(self.style.SUCCESS(f"Passed: {stats['passed']}"))
        self.stdout.write(self.style.ERROR(f"Failed: {stats['failed']}"))
        self.stdout.write(f"Failed exact-match cases: {stats['failed_exact_match']}")
        self.stdout.write(f"Failed brand-wide cases: {stats['failed_brand_wide']}")
        self.stdout.write(f"Failed duplicate-separation cases: {stats['failed_duplicate_separation']}")
        self.stdout.write(f"Failed technical-filter cases: {stats['failed_technical_filter']}")
        self.stdout.write(f"Failed ranking-order cases: {stats['failed_ranking_order']}")
        self._print_sep()
