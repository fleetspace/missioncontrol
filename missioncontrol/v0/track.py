from flask import request, Response
from home.leaf import LeafPassFile

DEF_STEP_S = 5


def get_track_file(access, step=DEF_STEP_S):
    accepts = request.headers.get("accept", "")
    if "application/vnd.leaf+json" in accepts:
        return (
            LeafPassFile.from_access(access).json,
            200,
            {"Content-Type": "application/json"},
        )
    if "application/vnd.leaf+text" in accepts:
        return Response(
            str(LeafPassFile.from_access(access)), mimetype="application/octet-stream"
        )
    return list(access.iter_track(step=step))
