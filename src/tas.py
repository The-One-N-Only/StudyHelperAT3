"""Technology and Applied Studies (TAS) subject tools."""

import logging

logger = logging.getLogger(__name__)

# Food technology: USDA nutrient database lookup
USDA_API_BASE = "https://api.nal.usda.gov/fdc/v1"

def search_food(query: str, api_key: str = "") -> list[dict]:
    """Search USDA FoodData Central for nutrition info."""
    if not api_key:
        return [{
            "source_name": "USDA FoodData Central",
            "title": f"Search results for: {query}",
            "source_url": f"https://fdc.nal.usda.gov/fdc-app.html#/?query={query}",
            "snippet": "Visit USDA FoodData Central for detailed nutrition information.",
        }]

    try:
        import requests
        resp = requests.get(
            f"{USDA_API_BASE}/foods/search",
            params={"api_key": api_key, "query": query, "pageSize": 5},
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            results = []
            for food in data.get("foods", []):
                nutrients = {}
                for nutrient in food.get("foodNutrients", [])[:10]:
                    name = nutrient.get("nutrientName", "")
                    value = nutrient.get("value", "")
                    unit = nutrient.get("unitName", "")
                    if name and value:
                        nutrients[name] = f"{value} {unit}"

                results.append({
                    "source_name": "USDA FoodData Central",
                    "title": food.get("description", "Unknown food"),
                    "source_url": f"https://fdc.nal.usda.gov/fdc-app.html#/food-details/{food.get('fdcId', '')}",
                    "snippet": f"Energy: {nutrients.get('Energy', 'N/A')} | Protein: {nutrients.get('Protein', 'N/A')} | Carbs: {nutrients.get('Carbohydrate, by difference', 'N/A')}",
                    "nutrients": nutrients,
                })
            return results
    except Exception as e:
        logger.error(f"USDA search failed: {e}")

    return []

# Materials property reference (expanded dataset)
MATERIALS_PROPERTIES = {
    "Steel - Mild": {"type": "Metal", "density_gcm3": 7.85, "tensile_strength_MPa": 400, "melting_point_C": 1370, "uses": "Construction, automotive body panels, structural"},
    "Steel - Stainless 304": {"type": "Metal", "density_gcm3": 8.0, "tensile_strength_MPa": 505, "melting_point_C": 1400, "uses": "Kitchen equipment, chemical plant, architectural"},
    "Aluminum 6061": {"type": "Metal", "density_gcm3": 2.7, "tensile_strength_MPa": 310, "melting_point_C": 652, "uses": "Aircraft, bike frames, marine fittings"},
    "Copper": {"type": "Metal", "density_gcm3": 8.96, "tensile_strength_MPa": 210, "melting_point_C": 1084, "uses": "Electrical wiring, plumbing, roofing"},
    "Oak - White": {"type": "Timber", "density_gcm3": 0.75, "tensile_strength_MPa": 100, "uses": "Furniture, flooring, construction timber"},
    "Pine - Radiata": {"type": "Timber", "density_gcm3": 0.5, "tensile_strength_MPa": 75, "uses": "Construction timber, furniture, joinery"},
    "Plywood": {"type": "Timber Composite", "density_gcm3": 0.6, "tensile_strength_MPa": 40, "uses": "Sheathing, formwork, furniture"},
    "MDF": {"type": "Timber Composite", "density_gcm3": 0.75, "tensile_strength_MPa": 30, "uses": "Furniture, shelving, cabinetry"},
    "Acrylic (PMMA)": {"type": "Polymer", "density_gcm3": 1.18, "tensile_strength_MPa": 72, "melting_point_C": 160, "uses": "Signage, displays, aquariums, lighting"},
    "Nylon 6/6": {"type": "Polymer", "density_gcm3": 1.14, "tensile_strength_MPa": 83, "melting_point_C": 263, "uses": "Gears, bearings, fasteners, textiles"},
    "PLA (3D Printing)": {"type": "Polymer", "density_gcm3": 1.24, "tensile_strength_MPa": 60, "melting_point_C": 173, "uses": "3D printing, prototypes, biodegradable"},
    "Concrete (Standard)": {"type": "Composite", "density_gcm3": 2.4, "compressive_strength_MPa": 25, "uses": "Foundations, slabs, columns, roads"},
    "Carbon Fiber (Epoxy)": {"type": "Composite", "density_gcm3": 1.6, "tensile_strength_MPa": 3500, "uses": "Aerospace, sporting goods, automotive"},
    "Glass (Soda-lime)": {"type": "Ceramic", "density_gcm3": 2.5, "tensile_strength_MPa": 50, "uses": "Windows, bottles, tableware"},
}

def search_materials(query: str) -> list[dict]:
    """Search materials property database."""
    query_lower = query.lower()
    results = []
    for name, props in MATERIALS_PROPERTIES.items():
        if query_lower in name.lower() or query_lower in props.get("type", "").lower():
            results.append({
                "source_name": "Materials Reference",
                "title": name,
                "description": " | ".join(f"{k}: {v}" for k, v in props.items()),
                "properties": props,
            })
    return results[:10]
