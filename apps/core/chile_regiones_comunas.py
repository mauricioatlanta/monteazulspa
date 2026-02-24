"""
Regiones y comunas de Chile (división administrativa).
Estructura: regiones por orden, comunas agrupadas por región.
"""
# Formato: (codigo, nombre) para regiones; comunas por codigo_region
REGIONES = [
    ("arica-parinacota", "Arica y Parinacota"),
    ("tarapaca", "Tarapacá"),
    ("antofagasta", "Antofagasta"),
    ("atacama", "Atacama"),
    ("coquimbo", "Coquimbo"),
    ("valparaiso", "Valparaíso"),
    ("metropolitana", "Metropolitana de Santiago"),
    ("ohiggins", "O'Higgins"),
    ("nuble", "Ñuble"),
    ("maule", "Maule"),
    ("biobio", "Biobío"),
    ("araucania", "La Araucanía"),
    ("los-rios", "Los Ríos"),
    ("los-lagos", "Los Lagos"),
    ("aysen", "Aysén"),
    ("magallanes", "Magallanes"),
]

# Comunas por codigo de región (ordenadas alfabéticamente dentro de cada región)
COMUNAS_POR_REGION = {
    "arica-parinacota": [
        "Arica", "Camarones", "General Lagos", "Putre",
    ],
    "tarapaca": [
        "Alto Hospicio", "Camiña", "Colchane", "Huara", "Iquique", "Pica", "Pozo Almonte",
    ],
    "antofagasta": [
        "Antofagasta", "Calama", "María Elena", "Mejillones", "Ollagüe", "San Pedro de Atacama",
        "Sierra Gorda", "Taltal", "Tocopilla",
    ],
    "atacama": [
        "Alto del Carmen", "Caldera", "Chañaral", "Copiapó", "Diego de Almagro",
        "Freirina", "Huasco", "Tierra Amarilla", "Vallenar",
    ],
    "coquimbo": [
        "Andacollo", "Canela", "Combarbalá", "Coquimbo", "Illapel", "La Higuera",
        "La Serena", "Los Vilos", "Monte Patria", "Ovalle", "Paiguano", "Punitaqui",
        "Río Hurtado", "Salamanca", "Vicuña",
    ],
    "valparaiso": [
        "Algarrobo", "Cabildo", "Calera", "Calle Larga", "Cartagena", "Casablanca",
        "Catemu", "Concón", "El Quisco", "El Tabo", "Hijuelas", "Isla de Pascua",
        "Juan Fernández", "La Cruz", "La Ligua", "Limache", "Llaillay", "Los Andes",
        "Nogales", "Olmué", "Panquehue", "Papudo", "Petorca", "Puchuncaví",
        "Putaendo", "Quilpué", "Quillota", "Quintero", "Rinconada", "San Antonio",
        "San Esteban", "San Felipe", "Santa María", "Santo Domingo", "Valparaíso",
        "Villa Alemana", "Viña del Mar", "Zapallar",
    ],
    "metropolitana": [
        "Alhué", "Buin", "Calera de Tango", "Cerrillos", "Cerro Navia", "Colina",
        "Conchalí", "Curacaví", "El Bosque", "El Monte", "Estación Central",
        "Huechuraba", "Independencia", "Isla de Maipo", "La Cisterna", "La Florida",
        "La Granja", "La Pintana", "La Reina", "Lampa", "Las Condes", "Lo Barnechea",
        "Lo Espejo", "Lo Prado", "Macul", "Maipú", "María Pinto", "Melipilla",
        "Ñuñoa", "Padre Hurtado", "Paine", "Pedro Aguirre Cerda", "Peñaflor",
        "Peñalolén", "Pirque", "Providencia", "Pudahuel", "Puente Alto", "Quilicura",
        "Quinta Normal", "Recoleta", "Renca", "San Bernardo", "San Joaquín",
        "San José de Maipo", "San Miguel", "San Pedro", "San Ramón", "Santiago",
        "Talagante", "Tiltil", "Vitacura",
    ],
    "ohiggins": [
        "Chépica", "Chimbarongo", "Codegua", "Coltauco", "Doñihue", "Graneros",
        "La Estrella", "Las Cabras", "Litueche", "Lolol", "Machalí", "Malloa",
        "Marchihue", "Mostazal", "Nancagua", "Navidad", "Olivar", "Palmilla",
        "Paredones", "Peralillo", "Peumo", "Pichidegua", "Pichilemu", "Placilla",
        "Pumanque", "Quinta de Tilcoco", "Rancagua", "Rengo", "Requínoa", "San Fernando",
        "San Vicente", "Santa Cruz",
    ],
    "nuble": [
        "Bulnes", "Chillán", "Chillán Viejo", "Cobquecura", "Coelemu", "Coihueco",
        "El Carmen", "Ninhue", "Ñiquén", "Pemuco", "Pinchas", "Portezuelo", "Quillón",
        "Quirihue", "Ránquil", "San Carlos", "San Fabián", "San Ignacio", "San Nicolás",
        "Treguaco", "Yungay",
    ],
    "maule": [
        "Cauquenes", "Chanco", "Colbún", "Constitución", "Curepto", "Curicó",
        "Empedrado", "Hualañé", "Licantén", "Linares", "Longaví", "Maule",
        "Molina", "Parral", "Pelarco", "Pelluhue", "Pencahue", "Rauco",
        "Retiro", "Río Claro", "Romeral", "Sagrada Familia", "San Clemente",
        "San Javier", "San Rafael", "Talca", "Teno", "Vichuquén", "Villa Alegre",
        "Yerbas Buenas",
    ],
    "biobio": [
        "Alto Biobío", "Antuco", "Arauco", "Cabrero", "Cañete", "Chiguayante",
        "Concepción", "Contulmo", "Coronel", "Curanilahue", "Florida", "Hualpén",
        "Hualqui", "Laja", "Lebu", "Los Álamos", "Los Ángeles", "Lota", "Mulchén",
        "Nacimiento", "Negrete", "Penco", "Quilaco", "Quilleco", "San Pedro de la Paz",
        "San Rosendo", "Santa Bárbara", "Santa Juana", "Talcahuano", "Tirúa",
        "Tomé", "Tucapel", "Yumbel",
    ],
    "araucania": [
        "Angol", "Carahue", "Cholchol", "Collipulli", "Cunco", "Curacautín",
        "Curarrehue", "Ercilla", "Freire", "Galvarino", "Gorbea", "Lautaro",
        "Loncoche", "Lonquimay", "Los Sauces", "Lumaco", "Melipeuco", "Nueva Imperial",
        "Padre Las Casas", "Perquenco", "Pitrufquén", "Pucón", "Purén", "Renaico",
        "Saavedra", "Temuco", "Teodoro Schmidt", "Toltén", "Traiguén", "Victoria",
        "Vilcún", "Villarrica",
    ],
    "los-rios": [
        "Corral", "Futrono", "La Unión", "Lago Ranco", "Lanco", "Los Lagos",
        "Mariquina", "Máfil", "Paillaco", "Panguipulli", "Río Bueno", "Valdivia",
    ],
    "los-lagos": [
        "Ancud", "Calbuco", "Castro", "Chaitén", "Chonchi", "Cochamó", "Curaco de Vélez",
        "Dalcahue", "Fresia", "Frutillar", "Futaleufú", "Hualaihué", "Llanquihue",
        "Los Muermos", "Maullín", "Osorno", "Palena", "Puerto Montt", "Puerto Octay",
        "Puerto Varas", "Puqueldón", "Purranque", "Puyehue", "Queilén", "Quellón",
        "Quemchi", "Quinchao", "Río Negro", "San Juan de la Costa", "San Pablo",
    ],
    "aysen": [
        "Aysén", "Chile Chico", "Cisnes", "Cochrane", "Guaitecas", "Lago Verde",
        "O'Higgins", "Río Ibáñez", "Tortel",
    ],
    "magallanes": [
        "Antártica", "Cabo de Hornos", "Laguna Blanca", "Natales", "Porvenir",
        "Primavera", "Punta Arenas", "Río Verde", "San Gregorio", "Timaukel",
        "Torres del Paine",
    ],
}


def get_regiones():
    """Retorna lista de regiones: [{"codigo": str, "nombre": str}, ...]"""
    return [{"codigo": c, "nombre": n} for c, n in REGIONES]


def get_comunas_por_region(codigo_region):
    """Retorna lista de comunas para una región. Si no existe, retorna []."""
    comunas = COMUNAS_POR_REGION.get(codigo_region, [])
    return [{"nombre": c} for c in comunas]
