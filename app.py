import streamlit as st
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

st.set_page_config(page_title="SkillSwap 2.0", page_icon="🔄", layout="wide", initial_sidebar_state="expanded")
DB = Path("skillswap.db")
NOW = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")

st.markdown("""
<style>
:root { --accent:#7c3aed; --mint:#34d399; }
.block-container {padding-top: 2rem; padding-bottom: 3rem;}
.hero {padding:2rem; border-radius:24px; background:linear-gradient(135deg,#21113f,#102a43); border:1px solid #49346b; margin-bottom:1.2rem;}
.hero h1 {font-size:2.7rem; margin-bottom:.3rem;}
.hero p {color:#cbd5e1; font-size:1.05rem;}
.card {padding:1rem 1.2rem; border:1px solid rgba(148,163,184,.25); border-radius:18px; background:rgba(15,23,42,.35); margin-bottom:.8rem;}
.badge {display:inline-block; padding:.2rem .55rem; border-radius:999px; font-size:.78rem; font-weight:700; background:#1e293b; color:#cbd5e1;}
.good {background:#064e3b; color:#6ee7b7;}
.warn {background:#713f12; color:#fde68a;}
.muted {color:#94a3b8; font-size:.9rem;}
</style>
""", unsafe_allow_html=True)


def db():
    return sqlite3.connect(DB, check_same_thread=False)


def column_exists(conn, table, column):
    return column in [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def ensure_column(conn, table, column, definition):
    if not column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = db(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL, bio TEXT DEFAULT '', availability TEXT DEFAULT 'Flexible',
        mode TEXT DEFAULT 'Online', created_at TEXT, verified INTEGER DEFAULT 0,
        verification_status TEXT DEFAULT 'Unverified', credits INTEGER DEFAULT 20,
        reputation REAL DEFAULT 0, completed_count INTEGER DEFAULT 0)""")
    cur.execute("CREATE TABLE IF NOT EXISTS skills(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)")
    cur.execute("""CREATE TABLE IF NOT EXISTS user_skills(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, skill_id INTEGER,
        skill_type TEXT, level TEXT, verification_status TEXT DEFAULT 'Self-declared')""")
    cur.execute("""CREATE TABLE IF NOT EXISTS evidence(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, skill_name TEXT,
        evidence_type TEXT, evidence_url TEXT, description TEXT, status TEXT DEFAULT 'Submitted', auto_score INTEGER DEFAULT 0, auto_notes TEXT DEFAULT '', created_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER, receiver_id INTEGER,
        message TEXT, status TEXT DEFAULT 'Pending', created_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS exchanges(
        id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER, user1 INTEGER, user2 INTEGER,
        skill_from_user1 TEXT DEFAULT '', skill_from_user2 TEXT DEFAULT '', scheduled_date TEXT DEFAULT '',
        scheduled_time TEXT DEFAULT '', status TEXT DEFAULT 'Active', completed_at TEXT,
        commitment_status TEXT DEFAULT 'Pending', session_notes TEXT DEFAULT '')""")
    cur.execute("""CREATE TABLE IF NOT EXISTS ratings(
        id INTEGER PRIMARY KEY AUTOINCREMENT, exchange_id INTEGER, rater_id INTEGER,
        rated_id INTEGER, rating INTEGER, comment TEXT DEFAULT '', created_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS notifications(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, message TEXT,
        is_read INTEGER DEFAULT 0, created_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER, reported_id INTEGER,
        reason TEXT, status TEXT DEFAULT 'Open', created_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS credit_ledger(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER,
        reason TEXT, exchange_id INTEGER, created_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS blocks(
        id INTEGER PRIMARY KEY AUTOINCREMENT, blocker_id INTEGER, blocked_id INTEGER,
        created_at TEXT, UNIQUE(blocker_id, blocked_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS ratings(
        id INTEGER PRIMARY KEY AUTOINCREMENT, exchange_id INTEGER, rater_id INTEGER,
        rated_id INTEGER, rating INTEGER, comment TEXT DEFAULT '', created_at TEXT,
        UNIQUE(exchange_id, rater_id))""")
    # Safe migration for older versions
    for table, col, definition in [
        ('users','verified','INTEGER DEFAULT 0'), ('users','verification_status',"TEXT DEFAULT 'Unverified'"),
        ('users','credits','INTEGER DEFAULT 20'), ('users','reputation','REAL DEFAULT 0'),
        ('users','completed_count','INTEGER DEFAULT 0'), ('user_skills','verification_status',"TEXT DEFAULT 'Self-declared'"),
        ('exchanges','commitment_status',"TEXT DEFAULT 'Pending'"), ('exchanges','session_notes',"TEXT DEFAULT ''"), ('evidence','auto_score','INTEGER DEFAULT 0'), ('evidence','auto_notes',"TEXT DEFAULT ''")]:
        ensure_column(conn, table, col, definition)
    conn.commit(); conn.close()


def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(name, email, password):
    conn = db()
    try:
        conn.execute("INSERT INTO users(name,email,password,created_at) VALUES(?,?,?,?)", (name.strip(), email.strip().lower(), hash_pw(password), NOW()))
        conn.commit(); return True
    except sqlite3.IntegrityError:
        return False
    finally: conn.close()


def login(email, password):
    conn = db(); row = conn.execute("SELECT id,name,email FROM users WHERE email=? AND password=?", (email.strip().lower(), hash_pw(password))).fetchone(); conn.close(); return row


def user(uid):
    conn = db(); row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone(); conn.close(); return row


def add_note(uid, title, message):
    conn = db(); conn.execute("INSERT INTO notifications(user_id,title,message,created_at) VALUES(?,?,?,?)", (uid,title,message,NOW())); conn.commit(); conn.close()


def unread(uid):
    conn = db(); n = conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (uid,)).fetchone()[0]; conn.close(); return n


def skills(uid, kind=None):
    conn = db(); q = """SELECT s.name, us.level, us.verification_status FROM user_skills us JOIN skills s ON s.id=us.skill_id WHERE us.user_id=?"""; args=[uid]
    if kind: q += " AND us.skill_type=?"; args.append(kind)
    rows = conn.execute(q + " ORDER BY s.name", args).fetchall(); conn.close(); return rows


def add_skill(uid, name, kind, level):
    name = name.strip().title()
    if not name: return False
    conn = db(); conn.execute("INSERT OR IGNORE INTO skills(name) VALUES(?)", (name,)); sid = conn.execute("SELECT id FROM skills WHERE name=?", (name,)).fetchone()[0]
    exists = conn.execute("SELECT id FROM user_skills WHERE user_id=? AND skill_id=? AND skill_type=?", (uid,sid,kind)).fetchone()
    if exists: conn.close(); return False
    conn.execute("INSERT INTO user_skills(user_id,skill_id,skill_type,level) VALUES(?,?,?,?)", (uid,sid,kind,level)); conn.commit(); conn.close(); return True


def remove_skill(uid, name, kind):
    conn = db(); conn.execute("DELETE FROM user_skills WHERE user_id=? AND skill_type=? AND skill_id=(SELECT id FROM skills WHERE name=?)", (uid,kind,name)); conn.commit(); conn.close()


def screen_evidence(etype, url, desc):
    """Rule-based pre-screening only; it never proves real expertise."""
    score = 0; checks = []
    clean_url = (url or '').strip().lower(); clean_desc = (desc or '').strip()
    if len(clean_desc) >= 80:
        score += 35; checks.append('Detailed explanation provided')
    elif len(clean_desc) >= 30:
        score += 20; checks.append('Basic explanation provided')
    else: checks.append('Add a more detailed explanation')
    if etype in ['GitHub project','Portfolio link','Certificate'] and clean_url.startswith(('http://','https://')):
        score += 30; checks.append('Web link format detected')
    elif etype in ['Sample work','Practical assessment']:
        score += 20; checks.append('Reviewer or practical assessment required')
    else: checks.append('Add a public evidence link where possible')
    if any(token in clean_url for token in ['github.com','gitlab.com','behance.net','drive.google.com','docs.google.com']):
        score += 25; checks.append('Recognized evidence-host domain detected')
    else: checks.append('Domain not automatically recognized')
    status = 'Auto-screened: Ready for review' if score >= 55 else 'Auto-screened: Needs more evidence'
    return min(score,100), status, '; '.join(checks)


def submit_evidence(uid, skill, etype, url, desc):
    score, status, notes = screen_evidence(etype, url, desc)
    conn = db(); conn.execute("INSERT INTO evidence(user_id,skill_name,evidence_type,evidence_url,description,status,auto_score,auto_notes,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (uid,skill,etype,url,desc,status,score,notes,NOW())); conn.commit(); conn.close()


def evidence_for(uid):
    conn=db(); rows=conn.execute("SELECT id,skill_name,evidence_type,evidence_url,description,status,auto_score,auto_notes,created_at FROM evidence WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall(); conn.close(); return rows

def match(my_id, other_id):
    mine_teach = {x[0].lower():x[1] for x in skills(my_id,'teach')}; mine_learn = {x[0].lower():x[1] for x in skills(my_id,'learn')}
    their_teach = {x[0].lower():x[1] for x in skills(other_id,'teach')}; their_learn = {x[0].lower():x[1] for x in skills(other_id,'learn')}
    can_learn = set(mine_learn) & set(their_teach); can_teach = set(mine_teach) & set(their_learn)
    score = (40 if can_learn else 0) + (30 if can_teach else 0); reasons=[]
    if can_learn: reasons.append('They teach a skill you want to learn.')
    if can_teach: reasons.append('You teach a skill they want to learn.')
    a,b=user(my_id),user(other_id)
    if a[5]==b[5] or a[5]=='Flexible' or b[5]=='Flexible': score+=15; reasons.append('Availability is compatible.')
    if a[6]==b[6] or a[6]=='Both' or b[6]=='Both': score+=10; reasons.append('Learning mode is compatible.')
    if can_learn: score+=5; reasons.append('There is at least one learning target.')
    return {'score':min(score,100),'learn':can_learn,'teach':can_teach,'reciprocal':bool(can_learn and can_teach),'reasons':reasons}


def send_request(sender, receiver, message):
    conn=db(); exists=conn.execute("SELECT id FROM requests WHERE sender_id=? AND receiver_id=? AND status='Pending'",(sender,receiver)).fetchone()
    if exists: conn.close(); return False
    conn.execute("INSERT INTO requests(sender_id,receiver_id,message,created_at) VALUES(?,?,?,?)",(sender,receiver,message,NOW())); conn.commit(); conn.close(); add_note(receiver,'New exchange request','You received a new skill exchange request.'); return True


def incoming(uid):
    conn=db(); rows=conn.execute("SELECT r.id,u.id,u.name,u.email,r.message,r.status,r.created_at FROM requests r JOIN users u ON u.id=r.sender_id WHERE r.receiver_id=? ORDER BY r.id DESC",(uid,)).fetchall(); conn.close(); return rows


def accept_request(rid):
    conn=db(); r=conn.execute("SELECT sender_id,receiver_id FROM requests WHERE id=?",(rid,)).fetchone()
    if not r: conn.close(); return
    conn.execute("UPDATE requests SET status='Accepted' WHERE id=?",(rid,)); conn.execute("INSERT INTO exchanges(request_id,user1,user2) VALUES(?,?,?)",(rid,r[0],r[1])); conn.commit(); conn.close(); add_note(r[0],'Request accepted','Your skill exchange request was accepted.')


def reject_request(rid):
    conn=db(); r=conn.execute("SELECT sender_id FROM requests WHERE id=?",(rid,)).fetchone(); conn.execute("UPDATE requests SET status='Rejected' WHERE id=?",(rid,)); conn.commit(); conn.close();
    if r: add_note(r[0],'Request declined','Your skill exchange request was declined.')


def exchanges(uid):
    conn=db(); rows=conn.execute("""SELECT e.id,e.user1,e.user2,e.skill_from_user1,e.skill_from_user2,e.scheduled_date,e.scheduled_time,e.status,e.commitment_status,u.name
    FROM exchanges e JOIN users u ON u.id=CASE WHEN e.user1=? THEN e.user2 ELSE e.user1 END WHERE e.user1=? OR e.user2=? ORDER BY e.id DESC""",(uid,uid,uid)).fetchall(); conn.close(); return rows


def update_exchange(eid, date, time, commitment, notes, status=None):
    conn=db(); q="UPDATE exchanges SET scheduled_date=?,scheduled_time=?,commitment_status=?,session_notes=?"; args=[date,time,commitment,notes]
    if status: q += ",status=?"; args.append(status)
    q += " WHERE id=?"; args.append(eid); conn.execute(q,args); conn.commit(); users=conn.execute("SELECT user1,user2 FROM exchanges WHERE id=?",(eid,)).fetchone(); conn.close()
    if users:
        for uid in users: add_note(uid,'Exchange updated',f'Exchange #{eid} has been updated.')


def credit_change(uid, amount, reason="Adjustment", exchange_id=None):
    conn=db()
    conn.execute("UPDATE users SET credits=MAX(0,credits+?) WHERE id=?",(amount,uid))
    conn.execute("INSERT INTO credit_ledger(user_id,amount,reason,exchange_id,created_at) VALUES(?,?,?,?,?)",(uid,amount,reason,exchange_id,NOW()))
    conn.commit(); conn.close()


def credit_history(uid):
    conn=db(); rows=conn.execute("SELECT amount,reason,exchange_id,created_at FROM credit_ledger WHERE user_id=? ORDER BY id DESC",(uid,)).fetchall(); conn.close(); return rows


def block_user(blocker, blocked):
    conn=db(); conn.execute("INSERT OR IGNORE INTO blocks(blocker_id,blocked_id,created_at) VALUES(?,?,?)",(blocker,blocked,NOW())); conn.commit(); conn.close()


def is_blocked(a,b):
    conn=db(); row=conn.execute("SELECT id FROM blocks WHERE (blocker_id=? AND blocked_id=?) OR (blocker_id=? AND blocked_id=?)",(a,b,b,a)).fetchone(); conn.close(); return row is not None


def save_rating(exchange_id, rater_id, rated_id, rating, comment):
    conn=db(); conn.execute("INSERT OR REPLACE INTO ratings(exchange_id,rater_id,rated_id,rating,comment,created_at) VALUES(?,?,?,?,?,?)",(exchange_id,rater_id,rated_id,rating,comment,NOW()));
    conn.execute("UPDATE users SET reputation=(SELECT COALESCE(AVG(rating),0) FROM ratings WHERE rated_id=?) WHERE id=?",(rated_id,rated_id)); conn.commit(); conn.close()


def has_rating(exchange_id, rater_id):
    conn=db(); row=conn.execute("SELECT id FROM ratings WHERE exchange_id=? AND rater_id=?",(exchange_id,rater_id)).fetchone(); conn.close(); return row is not None


def complete_exchange(eid, uid):
    conn=db(); row=conn.execute("SELECT user1,user2,status FROM exchanges WHERE id=?",(eid,)).fetchone()
    if not row or uid not in row[:2]: conn.close(); return False
    conn.execute("UPDATE exchanges SET status='Completed',completed_at=? WHERE id=?",(NOW(),eid)); conn.execute("UPDATE users SET completed_count=completed_count+1 WHERE id IN (?,?)",(row[0],row[1])); conn.commit(); conn.close()
    for person in row[:2]:
        credit_change(person,10,"Completed skill exchange",eid)
        add_note(person,'Exchange completed',f'Exchange #{eid} was marked completed.')
    return True


def report_user(reporter, reported, reason):
    conn=db(); conn.execute("INSERT INTO reports(reporter_id,reported_id,reason,created_at) VALUES(?,?,?,?)",(reporter,reported,reason,NOW())); conn.commit(); conn.close()


def init_state():
    st.session_state.setdefault('logged_in',False); st.session_state.setdefault('user_id',None)

init_db(); init_state()

st.sidebar.markdown('# 🔄 SkillSwap 2.0')
st.sidebar.caption('Exchange skills. Build trust. Grow together.')
st.sidebar.info('MAITRON prototype • SDG 8')

if not st.session_state.logged_in:
    page=st.sidebar.radio('Navigation',['🏠 Home','🔐 Login','📝 Register'])
else:
    uid=st.session_state.user_id; me=user(uid)
    nav=["🏠 Dashboard","👤 My Profile","🔎 Find Matches",f"📩 Requests ({unread(uid)})","🤝 My Exchanges","🛡️ Proof of Skill","🎓 Skill Passport","💳 Credit Wallet","🛡️ Safety Center","⭐ Ratings","🔔 Notifications"]
    page=st.sidebar.radio('Navigation',nav)
    st.sidebar.divider(); st.sidebar.write(f"👤 **{me[1]}**"); st.sidebar.metric('Skill Credits',me[10] if len(me)>10 else 20)
    if st.sidebar.button('🚪 Logout',use_container_width=True): st.session_state.logged_in=False; st.session_state.user_id=None; st.rerun()

if page=='🏠 Home':
    st.markdown('<div class="hero"><h1>🔄 SkillSwap 2.0</h1><p>Learn what you want by teaching what you know — with evidence screening, non-monetary learning points and accountability.</p></div>',unsafe_allow_html=True)
    c1,c2,c3,c4=st.columns(4); c1.metric('Core model','Skill-for-skill'); c2.metric('Trust','Evidence + reports'); c3.metric('Exchange','Credit-based'); c4.metric('Theme','SDG 8')
    st.subheader('How it works')
    cols=st.columns(4)
    for col,head,desc in zip(cols,['1. Build profile','2. Verify evidence','3. Exchange credits','4. Track progress'],['Add skills you teach and want to learn.','Submit project links or other evidence.','Request, commit, schedule and complete sessions.','Earn credits, ratings and Skill Passport progress.']):
        with col: st.markdown(f'<div class="card"><h4>{head}</h4><p>{desc}</p></div>',unsafe_allow_html=True)
    st.info('Example: You teach Python and want Canva. Another student teaches Canva and wants Python. SkillSwap identifies the reciprocal match.')
    st.subheader('Trust principles')
    st.write('Profiles distinguish self-declared skills from submitted evidence and verified skills. Users can report problems, track commitments and review completed exchanges.')

elif page=='📝 Register':
    st.title('📝 Create account')
    with st.form('register'):
        name=st.text_input('Full name'); email=st.text_input('Email'); password=st.text_input('Password',type='password'); confirm=st.text_input('Confirm password',type='password'); submit=st.form_submit_button('Create account',use_container_width=True)
    if submit:
        if not name or not email or not password: st.error('Complete all fields.')
        elif password!=confirm: st.error('Passwords do not match.')
        elif len(password)<6: st.error('Password must contain at least 6 characters.')
        elif create_user(name,email,password): st.success('Account created. Go to Login.')
        else: st.error('An account with this email already exists.')

elif page=='🔐 Login':
    st.title('🔐 Welcome back')
    with st.form('login'):
        email=st.text_input('Email'); password=st.text_input('Password',type='password'); submit=st.form_submit_button('Login',use_container_width=True)
    if submit:
        row=login(email,password)
        if row: st.session_state.logged_in=True; st.session_state.user_id=row[0]; st.rerun()
        else: st.error('Invalid email or password.')

elif page=='🏠 Dashboard':
    me=user(uid); teach=skills(uid,'teach'); learn=skills(uid,'learn'); ex=exchanges(uid)
    st.title(f'Welcome back, {me[1]} 👋')
    c1,c2,c3,c4=st.columns(4); c1.metric('Teaching skills',len(teach)); c2.metric('Learning goals',len(learn)); c3.metric('Credits',me[10]); c4.metric('Completed',me[12])
    st.subheader('Profile trust status')
    st.markdown(f'<span class="badge {"good" if me[8]=="Verified" else "warn"}">{me[8]}</span>',unsafe_allow_html=True)
    st.caption('Verification status is skill/profile specific and should not be treated as a universal identity guarantee.')
    st.subheader('Your next steps')
    st.write('1. Add teaching and learning skills. 2. Submit evidence. 3. Find a compatible partner. 4. Agree on a session and complete it.')

elif page=='👤 My Profile':
    st.title('👤 My Profile'); me=user(uid)
    with st.form('profile'):
        bio=st.text_area('About you',value=me[4] or ''); availability=st.selectbox('Availability',['Flexible','Weekdays','Weekends','Evenings'],index=['Flexible','Weekdays','Weekends','Evenings'].index(me[5]) if me[5] in ['Flexible','Weekdays','Weekends','Evenings'] else 0); mode=st.selectbox('Mode',['Online','Offline','Both'],index=['Online','Offline','Both'].index(me[6]) if me[6] in ['Online','Offline','Both'] else 0); save=st.form_submit_button('Save profile',use_container_width=True)
    if save:
        conn=db(); conn.execute('UPDATE users SET bio=?,availability=?,mode=? WHERE id=?',(bio,availability,mode,uid)); conn.commit(); conn.close(); st.success('Profile updated.')
    st.subheader('Your skills')
    for kind,label in [('teach','Can teach'),('learn','Want to learn')]:
        st.write(f'**{label}**'); rows=skills(uid,kind)
        if rows:
            for name,level,status in rows: st.write(f'• {name} — {level} — {status}')
        else: st.caption('No skills added yet.')
    with st.expander('Add a skill'):
        with st.form('addskill'):
            name=st.text_input('Skill name'); kind=st.selectbox('Type',[('teach','Can teach'),('learn','Want to learn')],format_func=lambda x:x[1]); level=st.selectbox('Level',['Beginner','Intermediate','Advanced']); go=st.form_submit_button('Add skill')
        if go:
            if add_skill(uid,name,kind[0],level): st.success('Skill added.'); st.rerun()
            else: st.warning('Skill already exists or is empty.')

elif page=='🔎 Find Matches':
    st.title('🔎 Find compatible partners')
    minimum=st.slider('Minimum match score',0,100,30,5)
    conn=db(); people=conn.execute('SELECT id,name,bio,verification_status,credits FROM users WHERE id!=?',(uid,)).fetchall(); conn.close()
    found=[]
    for person in people:
        result=match(uid,person[0])
        if result['score']>=minimum and (result['learn'] or result['teach']) and not is_blocked(uid,person[0]): found.append((person,result))
    found.sort(key=lambda x:x[1]['score'],reverse=True)
    if not found: st.info('No compatible matches yet. Try adding more skills or lowering the score filter.')
    for person,result in found:
        p, r=person,result
        with st.container(border=True):
            a,b=st.columns([3,1]);
            with a:
                st.subheader(f'{p[1]} • {r["score"]}% match')
                st.caption(p[2] or 'No bio added.')
                st.write('Learning from them:', ', '.join(sorted(r['learn'])) or '—')
                st.write('Teaching to them:', ', '.join(sorted(r['teach'])) or '—')
                st.write('Profile status:', p[3])
                if r['reciprocal']: st.success('🔁 Reciprocal match detected')
                for reason in r['reasons']: st.caption('✓ '+reason)
            with b:
                if st.button('Send request',key=f'req{p[0]}',use_container_width=True):
                    if send_request(uid,p[0],'I would like to explore a skill exchange with you.'): st.success('Request sent.'); st.rerun()
                if st.button('Report profile',key=f'rep{p[0]}',use_container_width=True):
                    report_user(uid,p[0],'Profile concern submitted from prototype.'); st.warning('Report recorded for review.')
                if st.button('Block profile',key=f'block{p[0]}',use_container_width=True):
                    block_user(uid,p[0]); st.success('Profile blocked from your matching results.'); st.rerun()

elif page.startswith('📩 Requests'):
    st.title('📩 Exchange requests')
    rows=incoming(uid)
    if not rows: st.info('No incoming requests.')
    for row in rows:
        rid,sid,name,email,message,status,created=row
        with st.container(border=True):
            st.subheader(f'{name} • {status}'); st.caption(created); st.write(message or 'No message.')
            if status=='Pending':
                c1,c2=st.columns(2)
                if c1.button('Accept',key=f'acc{rid}',use_container_width=True): accept_request(rid); st.success('Accepted.'); st.rerun()
                if c2.button('Reject',key=f'rej{rid}',use_container_width=True): reject_request(rid); st.warning('Rejected.'); st.rerun()

elif page=='🤝 My Exchanges':
    st.title('🤝 My exchanges')
    rows=exchanges(uid)
    if not rows: st.info('No exchanges yet. Find a match and send a request.')
    for row in rows:
        eid,u1,u2,s1,s2,date,time,status,commitment,partner=row
        with st.container(border=True):
            st.subheader(f'Exchange #{eid} with {partner}')
            st.write(f'Status: **{status}** | Commitment: **{commitment}**')
            with st.form(f'ex{eid}'):
                d=st.text_input('Date (YYYY-MM-DD)',value=date or '',key=f'd{eid}'); t=st.text_input('Time',value=time or '',key=f't{eid}'); c=st.selectbox('Commitment status',['Pending','Agreed','Reschedule requested','Cancelled'],index=['Pending','Agreed','Reschedule requested','Cancelled'].index(commitment) if commitment in ['Pending','Agreed','Reschedule requested','Cancelled'] else 0,key=f'c{eid}'); notes=st.text_area('Session notes',key=f'n{eid}'); save=st.form_submit_button('Save commitment')
            if save: update_exchange(eid,d,t,c,notes); st.success('Exchange updated.'); st.rerun()
            if status!='Completed' and st.button('Mark completed',key=f'complete{eid}'):
                if complete_exchange(eid,uid): st.success('Completed and credits updated.'); st.rerun()

elif page=='🛡️ Proof of Skill':
    st.title('🛡️ Proof of Skill')
    st.info('Automatic pre-screening checks evidence completeness, link format and recognized hosting domains. It does not claim that a person is skilled; final verification requires a reviewer or practical assessment.')
    with st.form('evidence'):
        skill=st.text_input('Skill being evidenced'); etype=st.selectbox('Evidence type',['GitHub project','Portfolio link','Certificate','Sample work','Practical assessment']); url=st.text_input('Evidence URL (optional)'); desc=st.text_area('Describe what the evidence demonstrates'); submit=st.form_submit_button('Submit evidence')
    if submit:
        if skill and desc: submit_evidence(uid,skill,etype,url,desc); st.success('Evidence submitted for review.'); st.rerun()
        else: st.warning('Add a skill and a short description.')
    st.subheader('Your evidence submissions')
    rows=evidence_for(uid)
    if not rows: st.caption('No evidence submitted yet.')
    for row in rows:
        eid,skill,etype,url,desc,status,auto_score,auto_notes,created=row
        with st.container(border=True):
            st.write(f'**{skill}** • {etype} • {status}'); st.caption(f'{created} • Automatic evidence score: {auto_score}/100'); st.write(desc); st.write(url or 'No URL provided'); st.caption(auto_notes)

    st.caption('Next verification step: reviewer checks the submitted work or conducts a short practical task before awarding a skill-specific Verified badge.')

elif page=='🎓 Skill Passport':
    st.title('🎓 Skill Passport')
    me=user(uid); c1,c2,c3=st.columns(3); c1.metric('Credits',me[10]); c2.metric('Completed exchanges',me[12]); c3.metric('Reputation',me[11])
    st.subheader('Learning record')
    for name,level,status in skills(uid): st.write(f'• **{name}** — {level} — {status}')
    st.caption('Future scope: reviewer-approved badges, downloadable reports and institution-backed verification.')

elif page=='💳 Credit Wallet':
    st.title('💳 Credit Wallet')
    me=user(uid)
    c1,c2=st.columns(2); c1.metric('Available credits',me[10]); c2.metric('Completed exchanges',me[12])
    st.info('Learning points are non-monetary: they cannot be withdrawn, sold, exchanged for cash, or used as payment. They only track participation and learning progress.')
    rows=credit_history(uid)
    if rows:
        st.subheader('Credit history')
        for amount,reason,eid,created in rows:
            sign='+' if amount>=0 else ''
            st.write(f'**{sign}{amount} credits** — {reason}'+(f' • Exchange #{eid}' if eid else '')+f' • {created}')
    else: st.caption('Your credit history will appear after your first recorded transaction.')

elif page=='🛡️ Safety Center':
    st.title('🛡️ Safety Center')
    st.info('Verification badges show the current review state of submitted evidence. They do not guarantee identity, expertise or personal safety.')
    st.subheader('Safety checklist')
    for item in ['Keep communication inside the platform where possible.', 'Do not share passwords, financial information or private documents.', 'Use public or institution-approved locations for offline meetings.', 'Report suspicious behaviour and cancel unsafe sessions.', 'Review a partner’s evidence, reputation and completed exchanges.']:
        st.checkbox(item, value=False, key='safe_'+str(abs(hash(item))))
    st.subheader('Report a user')
    conn=db(); people=conn.execute('SELECT id,name,email FROM users WHERE id!=?',(uid,)).fetchall(); conn.close()
    if people:
        target=st.selectbox('User',people,format_func=lambda x:f'{x[1]} ({x[2]})')
        reason=st.text_area('Reason for report')
        if st.button('Submit safety report'):
            if reason.strip(): report_user(uid,target[0],reason.strip()); st.success('Report submitted for review.')
            else: st.warning('Please describe the concern.')
    else: st.caption('No other users available.')

elif page=='⭐ Ratings':
    st.title('⭐ Ratings and reputation')
    st.caption('Rate only exchanges you have completed. Ratings should be honest and respectful.')
    rows=exchanges(uid)
    if not rows: st.info('Complete an exchange before rating a partner.')
    for row in rows:
        eid,u1,u2,s1,s2,date,time,status,commitment,partner=row
        partner_id=u2 if u1==uid else u1
        if status=='Completed':
            st.write(f'**Exchange #{eid} with {partner}**')
            if has_rating(eid,uid): st.success('You have already rated this exchange.')
            else:
                with st.form(f'rating_{eid}'):
                    rating=st.slider('Rating',1,5,5,key=f'rate_{eid}')
                    comment=st.text_area('Comment',key=f'comment_{eid}')
                    submit=st.form_submit_button('Submit rating')
                if submit:
                    save_rating(eid,uid,partner_id,rating,comment); st.success('Rating saved.'); st.rerun()

elif page=='🔔 Notifications':
    st.title('🔔 Notifications')
    conn=db(); rows=conn.execute('SELECT title,message,is_read,created_at FROM notifications WHERE user_id=? ORDER BY id DESC',(uid,)).fetchall(); conn.execute('UPDATE notifications SET is_read=1 WHERE user_id=?',(uid,)); conn.commit(); conn.close()
    if not rows: st.info('No notifications yet.')
    for title,message,read,created in rows:
        with st.container(border=True): st.write(f'**{title}**'); st.write(message); st.caption(created)

st.divider(); st.caption('SkillSwap 2.0 • Prototype for MAITRON 2026 • Skill-for-skill, with trust and accountability.')
