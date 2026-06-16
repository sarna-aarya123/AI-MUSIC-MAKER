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
      genre   : "rage" | "pluggnb" | "dark_trap" | "cloud"
      root    : "A" .. "G#"
      bpm     : int  (overrides genre default)
      bars    : int  (max loop bars — actual may be shorter)
      seed    : int  (reproducible generation)

    Returns full loop identity: motif, bass, textures, bpm, loop_length, …
    """
    body = request.get_json(silent=True) or {}

    genre = body.get('genre', 'rage')
    root  = body.get('root',  'A')
    bars  = int(body.get('bars', 4))
    seed  = body.get('seed')
    bpm   = body.get('bpm')

    if bpm is not None:
        bpm = int(bpm)
    if seed is not None:
        seed = int(seed)

    loop = generate_loop(genre=genre, root=root, bpm=bpm, bars=bars, seed=seed)
    return jsonify(loop)
