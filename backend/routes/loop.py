"""
loop.py — Blueprint for /api/loop routes.
"""
from flask import Blueprint, request, jsonify
from backend.services.loop_service import generate_loop

loop_bp = Blueprint('loop', __name__, url_prefix='/api/loop')


@loop_bp.route('/evolve', methods=['POST'])
def evolve():
    """
    POST /api/loop/evolve

    Body (all optional):
      genre           : "rage" | "pluggnb" | "dark_trap" | "cloud"
      root            : "A" .. "G#"
      bpm             : int  (overrides genre default)
      bars            : int  (max loop bars)
      seed            : int  (reproducible generation)
      description     : str  (free text — parsed keywords override genre/instrument)
      lead_instrument : "bell" | "pluck" | "saw_lead" | "fm_lead" | "glass" | "square"
    """
    body = request.get_json(silent=True) or {}

    genre           = body.get('genre', 'rage')
    root            = body.get('root',  'A')
    bars            = int(body.get('bars', 4))
    seed            = body.get('seed')
    bpm             = body.get('bpm')
    description     = body.get('description', '').strip() or None
    lead_instrument = body.get('lead_instrument') or None

    if bpm is not None:
        bpm = int(bpm)
    if seed is not None:
        seed = int(seed)

    loop = generate_loop(
        genre=genre, root=root, bpm=bpm, bars=bars, seed=seed,
        description=description, lead_instrument=lead_instrument,
    )
    return jsonify(loop)
