"""
Face recognition routes using InsightFace (ArcFace).
Falls back to OpenCV + DeepFace if insightface not available.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from src.extention import db
from src.models.worker_model import Worker
from src.models.attendance_model import AttendanceRecord
import os, base64, json, threading
import numpy as np
from datetime import date, datetime
from src.apptime import now as app_now, today as app_today

face_bp = Blueprint('face', __name__)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'uploads', 'workers')
SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'uploads', 'snapshots')
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# ---------- AI Engine Init ----------
_face_engine = None
_use_insightface = False
# The server handles requests on several threads now. Loading guards against two threads
# each building a model; inference is serialised because one frame already saturates the
# CPU, and running two at once only makes both slower while starving other requests.
_load_lock = threading.Lock()
_infer_lock = threading.Lock()

def _get_engine():
    global _face_engine, _use_insightface
    if _face_engine is not None:
        return _face_engine, _use_insightface

    with _load_lock:
        if _face_engine is not None:
            return _face_engine, _use_insightface

        try:
            import insightface
            from insightface.app import FaceAnalysis
            app = FaceAnalysis(name='buffalo_sc', providers=['CPUExecutionProvider'])
            app.prepare(ctx_id=0, det_size=(320, 320))
            _face_engine = app
            _use_insightface = True
            print("[FACE] Using InsightFace engine")
            return _face_engine, _use_insightface
        except Exception as e:
            print(f"[FACE] InsightFace not available ({e}), trying DeepFace...")

        try:
            from deepface import DeepFace
            _face_engine = DeepFace
            _use_insightface = False
            print("[FACE] Using DeepFace engine")
            return _face_engine, _use_insightface
        except Exception as e:
            print(f"[FACE] DeepFace also failed ({e}). Face recognition unavailable.")
            return None, False


def warm_engine():
    """Load the model ahead of the first request (gunicorn calls this after each worker starts)."""
    engine, use_insight = _get_engine()
    kind = 'insightface' if use_insight else ('deepface' if engine else 'none')
    print(f"[FACE] Warm-up finished: engine={kind}")


def _b64_to_np(b64_str):
    """Convert base64 image to numpy array."""
    import cv2
    if ',' in b64_str:
        b64_str = b64_str.split(',')[1]
    img_bytes = base64.b64decode(b64_str)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img


def _extract_embedding(img_np):
    """Extract embedding from numpy image, return list of floats or None."""
    engine, use_insight = _get_engine()
    if engine is None:
        return None

    if use_insight:
        with _infer_lock:
            faces = engine.get(img_np)
        if not faces:
            return None
        return faces[0].embedding.tolist()
    else:
        import cv2, tempfile
        from deepface import DeepFace
        tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        cv2.imwrite(tmp.name, img_np)
        try:
            emb = DeepFace.represent(img_path=tmp.name, model_name='Facenet512',
                                     enforce_detection=True, detector_backend='opencv')
            return emb[0]['embedding']
        except Exception:
            return None
        finally:
            os.unlink(tmp.name)


def _cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / (norm + 1e-10))


# ---------- Routes ----------

@face_bp.route('/register', methods=['POST'])
@jwt_required()
def register_face():
    """
    Register face embeddings for a worker.
    Expects: { worker_id, frames: [base64, ...] }  (5-10 frames)
    """
    data = request.get_json()
    worker_id = data.get('worker_id')
    frames = data.get('frames', [])

    if not worker_id or not frames:
        return jsonify({'error': 'worker_id and frames required'}), 400

    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({'error': 'Worker not found'}), 404

    engine, _ = _get_engine()
    if engine is None:
        return jsonify({'error': 'Face recognition engine not available'}), 503

    print(f"[FACE] Registering face for worker {worker_id}...")
    embeddings = []
    for i, frame in enumerate(frames):
        try:
            img_np = _b64_to_np(frame)
            emb = _extract_embedding(img_np)
            if emb:
                embeddings.append(emb)
                print(f"[FACE] Frame {i+1} embedding extracted")
            else:
                print(f"[FACE] Frame {i+1} NO face detected")
        except Exception as ex:
            print(f"[FACE] Frame {i+1} error: {ex}")

    if len(embeddings) < 1:
        print("[FACE] ERROR: No face embeddings collected")
        return jsonify({'error': 'No valid faces detected in provided frames'}), 422

    # Average the embeddings for robustness
    avg_embedding = np.mean(embeddings, axis=0).tolist()
    worker.set_embedding(avg_embedding)
    print(f"[FACE] SUCCESS: Saved average embedding (length {len(avg_embedding)}) to worker {worker.worker_code}")

    # Save first good frame as photo if not set
    if not worker.photo_path and frames:
        try:
            img_np = _b64_to_np(frames[0])
            import cv2
            path = os.path.join(UPLOAD_DIR, f'{worker.worker_code}.jpg')
            cv2.imwrite(path, img_np)
            worker.photo_path = path
        except Exception:
            pass

    db.session.commit()
    return jsonify({
        'message': f'Face registered with {len(embeddings)} frames',
        'worker': worker.to_dict()
    }), 200


@face_bp.route('/recognize', methods=['POST'])
@jwt_required()
def recognize():
    """
    Face-based check-in / check-out.
    Expects: { frame: base64, mode: 'checkin'|'checkout', plant_id (optional) }
    Returns matched worker + creates/updates attendance record.
    """
    data = request.get_json()
    frame_b64 = data.get('frame')
    mode = data.get('mode', 'checkin')  # 'checkin' or 'checkout'

    if not frame_b64:
        return jsonify({'error': 'frame required'}), 400

    engine, _ = _get_engine()
    if engine is None:
        return jsonify({'error': 'Face recognition engine not available'}), 503

    # Extract embedding from incoming frame
    try:
        img_np = _b64_to_np(frame_b64)
        query_emb = _extract_embedding(img_np)
    except Exception as ex:
        return jsonify({'error': f'Could not process frame: {str(ex)}'}), 422

    if query_emb is None:
        return jsonify({'error': 'No face detected in frame', 'match': False}), 422

    # Load all worker embeddings and find best match
    workers = Worker.query.filter(Worker.face_embedding.isnot(None), Worker.is_active == True).all()
    print(f"[FACE] Searching for match among {len(workers)} registered workers...")
    if not workers:
        return jsonify({'error': 'No registered faces in system', 'match': False}), 404

    THRESHOLD = 0.65  # cosine similarity threshold
    best_score = -1
    best_worker = None

    for w in workers:
        emb = w.get_embedding()
        if emb:
            score = _cosine_similarity(query_emb, emb)
            if score > best_score:
                best_score = score
                best_worker = w

    print(f"[FACE] Best match: {best_worker.name if best_worker else 'None'} (Score: {best_score:.4f})")
    if best_score < THRESHOLD:
        return jsonify({
            'match': False,
            'confidence': round(best_score, 4),
            'message': 'No matching face found'
        }), 200

    # Save snapshot
    snapshot_path = None
    try:
        import cv2
        ts = app_now().strftime('%Y%m%d_%H%M%S')
        snap_name = f'{best_worker.worker_code}_{ts}.jpg'
        snapshot_path = os.path.join(SNAPSHOT_DIR, snap_name)
        cv2.imwrite(snapshot_path, img_np)
    except Exception:
        pass

    # Create/Update attendance record
    today = app_today()
    now_time = app_now().time()

    if mode == 'checkin':
        # Lock the worker row so repeated live scans cannot create duplicate
        # open records for the same worker.
        best_worker = Worker.query.filter_by(id=best_worker.id).with_for_update().first()
        record = AttendanceRecord.query.filter_by(worker_id=best_worker.id, live_status='IN').order_by(AttendanceRecord.id.asc()).first()
        if record:
            return jsonify({
                'match': True,
                'already_checked_in': True,
                'worker': best_worker.to_dict(),
                'confidence': round(best_score, 4),
                'record': record.to_dict()
            }), 200

        record = AttendanceRecord(
            worker_id=best_worker.id,
            date=today,
            shift_type=best_worker.shift_type,
            checkin_time=now_time,
            checkin_photo=snapshot_path,
            live_status='IN',
            status='Present',
        )
        db.session.add(record)

    elif mode == 'checkout':
        best_worker = Worker.query.filter_by(id=best_worker.id).with_for_update().first()
        record = AttendanceRecord.query.filter_by(worker_id=best_worker.id, live_status='IN').order_by(AttendanceRecord.id.asc()).first()
        if not record:
            return jsonify({
                'match': True,
                'not_checked_in': True,
                'worker': best_worker.to_dict(),
                'confidence': round(best_score, 4),
            }), 200

        record.checkout_time = now_time
        record.checkout_date = today
        record.checkout_photo = snapshot_path
        record.live_status = 'OUT'
        record.calculate_hours()

    db.session.commit()
    return jsonify({
        'match': True,
        'mode': mode,
        'confidence': round(best_score, 4),
        'worker': best_worker.to_dict(),
        'record': record.to_dict()
    }), 200


@face_bp.route('/status', methods=['GET'])
def status():
    engine, use_insight = _get_engine()
    return jsonify({
        'available': engine is not None,
        'engine': 'insightface' if use_insight else ('deepface' if engine else 'none'),
    }), 200
