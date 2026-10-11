import argparse, time, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2]/'.env')
from sqlalchemy import select
from .database import SessionLocal
from .platform_models import SyncJob, User
from .auth import Principal
from .main import sync_step
from .anti_entropy import reconcile_due

def process_once():
    with SessionLocal() as db:
        controllers=db.scalars(select(User).where(User.role.in_(['owner','controller']))).all()
        actors={u.org_id:Principal(u.org_id,u.id,u.role,u.name) for u in controllers}
    for actor in actors.values():
        with SessionLocal() as db:
            reconcile_due(db,actor);db.commit()
    with SessionLocal() as db:
        jobs=db.scalars(select(SyncJob).where(SyncJob.status.in_(['queued','running','failed'])).order_by(SyncJob.created_at).limit(20)).all()
        ids=[(j.id,j.result.get('actor_id')) for j in jobs]
    for job_id,user_id in ids:
        with SessionLocal() as db:
            user=db.get(User,user_id) if user_id else None
            if not user or user.role not in ('owner','controller'): continue
            actor=Principal(user.org_id,user.id,user.role,user.name)
            result=sync_step(job_id,actor,db)
            print(job_id,result.get('status'),flush=True)
    return len(ids)

if __name__=='__main__':
    from .pqc_security import keys
    keys()
    from .database import Base, engine
    if os.getenv('FINANCE_AUTO_CREATE','true').lower()=='true': Base.metadata.create_all(engine)
    parser=argparse.ArgumentParser(description='Single-worker finance sync runner')
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    while True:
        process_once()
        if args.once: break
        time.sleep(5)
