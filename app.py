import streamlit as st
import sqlite3
import hashlib
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="SkillSwap",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB = "skillswap.db"


# ============================================================
# DATABASE
# ============================================================

def get_db():
    return sqlite3.connect(DB, check_same_thread=False)


def init_database():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            bio TEXT DEFAULT '',
            availability TEXT DEFAULT 'Flexible',
            mode TEXT DEFAULT 'Online',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            skill_id INTEGER NOT NULL,
            skill_type TEXT NOT NULL,
            level TEXT NOT NULL,

            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(skill_id) REFERENCES skills(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS exchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            user1 INTEGER NOT NULL,
            user2 INTEGER NOT NULL,
            skill_from_user1 TEXT DEFAULT '',
            skill_from_user2 TEXT DEFAULT '',
            scheduled_date TEXT DEFAULT '',
            scheduled_time TEXT DEFAULT '',
            status TEXT DEFAULT 'Active',
            completed_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange_id INTEGER NOT NULL,
            rater_id INTEGER NOT NULL,
            rated_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT DEFAULT '',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


init_database()


# ============================================================
# SECURITY
# ============================================================

def hash_password(password):
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


# ============================================================
# USER FUNCTIONS
# ============================================================

def create_user(name, email, password):

    conn = get_db()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO users
            (name, email, password, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            name.strip(),
            email.strip().lower(),
            hash_password(password),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        return True

    except sqlite3.IntegrityError:

        return False

    finally:

        conn.close()


def login_user(email, password):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, email
        FROM users
        WHERE email = ?
        AND password = ?
    """, (
        email.strip().lower(),
        hash_password(password)
    ))

    result = cur.fetchone()

    conn.close()

    return result


def get_user(user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (user_id,))

    result = cur.fetchone()

    conn.close()

    return result


def update_profile(
    user_id,
    bio,
    availability,
    mode
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users

        SET bio = ?,
            availability = ?,
            mode = ?

        WHERE id = ?
    """, (
        bio,
        availability,
        mode,
        user_id
    ))

    conn.commit()
    conn.close()


# ============================================================
# SKILL FUNCTIONS
# ============================================================

def get_or_create_skill(skill_name):

    skill_name = skill_name.strip().title()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO skills(name)
        VALUES (?)
    """, (skill_name,))

    conn.commit()

    cur.execute("""
        SELECT id
        FROM skills
        WHERE name = ?
    """, (skill_name,))

    skill_id = cur.fetchone()[0]

    conn.close()

    return skill_id


def add_skill(
    user_id,
    skill_name,
    skill_type,
    level
):

    if not skill_name.strip():
        return False

    skill_id = get_or_create_skill(
        skill_name
    )

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM user_skills

        WHERE user_id = ?
        AND skill_id = ?
        AND skill_type = ?
    """, (
        user_id,
        skill_id,
        skill_type
    ))

    if cur.fetchone():

        conn.close()
        return False

    cur.execute("""
        INSERT INTO user_skills
        (user_id, skill_id, skill_type, level)

        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        skill_id,
        skill_type,
        level
    ))

    conn.commit()
    conn.close()

    return True


def get_skills(user_id, skill_type):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            skills.name,
            user_skills.level

        FROM user_skills

        JOIN skills
        ON skills.id = user_skills.skill_id

        WHERE user_skills.user_id = ?
        AND user_skills.skill_type = ?

        ORDER BY skills.name
    """, (
        user_id,
        skill_type
    ))

    result = cur.fetchall()

    conn.close()

    return result


def delete_skill(
    user_id,
    skill_name,
    skill_type
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM user_skills

        WHERE user_id = ?
        AND skill_type = ?

        AND skill_id = (
            SELECT id
            FROM skills
            WHERE name = ?
        )
    """, (
        user_id,
        skill_type,
        skill_name
    ))

    conn.commit()
    conn.close()


# ============================================================
# NOTIFICATIONS
# ============================================================

def add_notification(
    user_id,
    title,
    message
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO notifications
        (user_id, title, message, created_at)

        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        title,
        message,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    conn.commit()
    conn.close()


def get_notifications(user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, message, is_read, created_at

        FROM notifications

        WHERE user_id = ?

        ORDER BY id DESC
    """, (user_id,))

    result = cur.fetchall()

    conn.close()

    return result


def unread_count(user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)

        FROM notifications

        WHERE user_id = ?
        AND is_read = 0
    """, (user_id,))

    result = cur.fetchone()[0]

    conn.close()

    return result


def mark_notifications_read(user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE notifications
        SET is_read = 1

        WHERE user_id = ?
    """, (user_id,))

    conn.commit()
    conn.close()


# ============================================================
# SMART MATCHING ENGINE
# ============================================================

LEVEL_SCORE = {
    "Beginner": 1,
    "Intermediate": 2,
    "Advanced": 3
}


def calculate_match(my_id, other_id):

    my_teach = {
        skill[0].lower(): skill[1]
        for skill in get_skills(
            my_id,
            "teach"
        )
    }

    my_learn = {
        skill[0].lower(): skill[1]
        for skill in get_skills(
            my_id,
            "learn"
        )
    }

    other_teach = {
        skill[0].lower(): skill[1]
        for skill in get_skills(
            other_id,
            "teach"
        )
    }

    other_learn = {
        skill[0].lower(): skill[1]
        for skill in get_skills(
            other_id,
            "learn"
        )
    }

    # What they can teach me
    can_learn = set(my_learn) & set(other_teach)

    # What I can teach them
    can_teach = set(my_teach) & set(other_learn)

    score = 0
    reasons = []

    # --------------------------------------------------------
    # LEARNING COMPATIBILITY
    # --------------------------------------------------------

    if can_learn:

        score += 40

        reasons.append(
            "They teach a skill you want to learn."
        )

    # --------------------------------------------------------
    # RECIPROCAL COMPATIBILITY
    # --------------------------------------------------------

    if can_teach:

        score += 30

        reasons.append(
            "You teach a skill they want to learn."
        )

    # --------------------------------------------------------
    # USER DATA
    # --------------------------------------------------------

    me = get_user(my_id)
    other = get_user(other_id)

    if me and other:

        # Availability
        if (
            me[5] == other[5]
            or me[5] == "Flexible"
            or other[5] == "Flexible"
        ):

            score += 15

            reasons.append(
                "Availability is compatible."
            )

        # Learning mode
        if (
            me[6] == other[6]
            or me[6] == "Both"
            or other[6] == "Both"
        ):

            score += 10

            reasons.append(
                "Preferred learning mode is compatible."
            )

    # --------------------------------------------------------
    # LEVEL COMPATIBILITY
    # --------------------------------------------------------

    level_match = False

    for skill in can_learn:

        learner_level = LEVEL_SCORE.get(
            my_learn[skill],
            1
        )

        teacher_level = LEVEL_SCORE.get(
            other_teach[skill],
            1
        )

        if teacher_level >= learner_level:

            level_match = True
            break

    if level_match:

        score += 5

        reasons.append(
            "Skill levels are compatible."
        )

    score = min(score, 100)

    reciprocal = bool(
        can_learn and can_teach
    )

    return {
        "score": score,
        "can_learn": can_learn,
        "can_teach": can_teach,
        "reciprocal": reciprocal,
        "reasons": reasons
    }


# ============================================================
# REQUESTS
# ============================================================

def request_exists(
    sender_id,
    receiver_id
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id

        FROM requests

        WHERE sender_id = ?
        AND receiver_id = ?
        AND status = 'Pending'
    """, (
        sender_id,
        receiver_id
    ))

    result = cur.fetchone()

    conn.close()

    return result is not None


def send_request(
    sender_id,
    receiver_id,
    message
):

    if request_exists(
        sender_id,
        receiver_id
    ):

        return False

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO requests
        (
            sender_id,
            receiver_id,
            message,
            status,
            created_at
        )

        VALUES (?, ?, ?, 'Pending', ?)
    """, (
        sender_id,
        receiver_id,
        message,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    conn.commit()
    conn.close()

    sender = get_user(sender_id)

    add_notification(
        receiver_id,
        "📩 New Skill Exchange Request",
        f"{sender[1]} wants to exchange skills with you."
    )

    return True


def incoming_requests(user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            requests.id,
            users.id,
            users.name,
            users.email,
            requests.message,
            requests.status,
            requests.created_at

        FROM requests

        JOIN users
        ON users.id = requests.sender_id

        WHERE requests.receiver_id = ?

        ORDER BY requests.id DESC
    """, (user_id,))

    result = cur.fetchall()

    conn.close()

    return result


def sent_requests(user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            requests.id,
            users.name,
            requests.status,
            requests.created_at

        FROM requests

        JOIN users
        ON users.id = requests.receiver_id

        WHERE requests.sender_id = ?

        ORDER BY requests.id DESC
    """, (user_id,))

    result = cur.fetchall()

    conn.close()

    return result


# ============================================================
# EXCHANGE FUNCTIONS
# ============================================================

def accept_request(request_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            sender_id,
            receiver_id
        FROM requests
        WHERE id = ?
    """, (request_id,))

    request = cur.fetchone()

    if not request:

        conn.close()
        return

    sender_id, receiver_id = request

    cur.execute("""
        UPDATE requests

        SET status = 'Accepted'

        WHERE id = ?
    """, (request_id,))

    cur.execute("""
        SELECT id
        FROM exchanges
        WHERE request_id = ?
    """, (request_id,))

    existing = cur.fetchone()

    if not existing:

        cur.execute("""
            INSERT INTO exchanges
            (
                request_id,
                user1,
                user2,
                status
            )

            VALUES (?, ?, ?, 'Active')
        """, (
            request_id,
            sender_id,
            receiver_id
        ))

    conn.commit()
    conn.close()

    receiver = get_user(receiver_id)

    add_notification(
        sender_id,
        "🤝 Request Accepted",
        f"{receiver[1]} accepted your skill exchange request."
    )


def reject_request(request_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE requests

        SET status = 'Rejected'

        WHERE id = ?
    """, (request_id,))

    cur.execute("""
        SELECT sender_id
        FROM requests
        WHERE id = ?
    """, (request_id,))

    sender = cur.fetchone()

    conn.commit()
    conn.close()

    if sender:

        add_notification(
            sender[0],
            "Request Update",
            "Your skill exchange request was declined."
        )


def get_exchanges(user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            exchanges.id,
            exchanges.user1,
            exchanges.user2,
            exchanges.skill_from_user1,
            exchanges.skill_from_user2,
            exchanges.scheduled_date,
            exchanges.scheduled_time,
            exchanges.status,
            users.name

        FROM exchanges

        JOIN users
        ON users.id =
            CASE
                WHEN exchanges.user1 = ?
                THEN exchanges.user2
                ELSE exchanges.user1
            END

        WHERE exchanges.user1 = ?
        OR exchanges.user2 = ?

        ORDER BY exchanges.id DESC
    """, (
        user_id,
        user_id,
        user_id
    ))

    result = cur.fetchall()

    conn.close()

    return result


def schedule_exchange(
    exchange_id,
    date,
    time
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE exchanges

        SET scheduled_date = ?,
            scheduled_time = ?

        WHERE id = ?
    """, (
        date,
        time,
        exchange_id
    ))

    conn.commit()

    cur.execute("""
        SELECT user1, user2
        FROM exchanges
        WHERE id = ?
    """, (exchange_id,))

    users = cur.fetchone()

    conn.close()

    if users:

        add_notification(
            users[0],
            "📅 Exchange Scheduled",
            f"Your skill exchange is scheduled for {date} at {time}."
        )

        add_notification(
            users[1],
            "📅 Exchange Scheduled",
            f"Your skill exchange is scheduled for {date} at {time}."
        )


def complete_exchange(exchange_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE exchanges

        SET status = 'Completed',
            completed_at = ?

        WHERE id = ?
    """, (
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        exchange_id
    ))

    conn.commit()
    conn.close()


# ============================================================
# RATINGS
# ============================================================

def has_rated(
    exchange_id,
    rater_id
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id

        FROM ratings

        WHERE exchange_id = ?
        AND rater_id = ?
    """, (
        exchange_id,
        rater_id
    ))

    result = cur.fetchone()

    conn.close()

    return result is not None


def submit_rating(
    exchange_id,
    rater_id,
    rated_id,
    rating,
    comment
):

    if has_rated(
        exchange_id,
        rater_id
    ):

        return False

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO ratings
        (
            exchange_id,
            rater_id,
            rated_id,
            rating,
            comment,
            created_at
        )

        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        exchange_id,
        rater_id,
        rated_id,
        rating,
        comment,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    conn.commit()
    conn.close()

    add_notification(
        rated_id,
        "⭐ New Rating",
        f"You received a {rating}/5 rating."
    )

    return True


def get_average_rating(user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT AVG(rating)

        FROM ratings

        WHERE rated_id = ?
    """, (user_id,))

    result = cur.fetchone()[0]

    conn.close()

    return round(result, 1) if result else 0


# ============================================================
# STATISTICS
# ============================================================

def get_statistics(user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM user_skills
        WHERE user_id = ?
    """, (user_id,))

    total_skills = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM exchanges
        WHERE
            (user1 = ? OR user2 = ?)
            AND status = 'Completed'
    """, (
        user_id,
        user_id
    ))

    completed = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM exchanges
        WHERE
            (user1 = ? OR user2 = ?)
            AND status = 'Active'
    """, (
        user_id,
        user_id
    ))

    active = cur.fetchone()[0]

    conn.close()

    rating = get_average_rating(
        user_id
    )

    return (
        total_skills,
        active,
        completed,
        rating
    )


# ============================================================
# SESSION STATE
# ============================================================

if "logged_in" not in st.session_state:

    st.session_state.logged_in = False

if "user_id" not in st.session_state:

    st.session_state.user_id = None


# ============================================================
# CUSTOM DESIGN
# ============================================================

st.markdown("""
<style>

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
}

.hero {
    padding: 25px;
    border-radius: 20px;
    background: linear-gradient(
        135deg,
        #1e293b,
        #0f172a
    );
    margin-bottom: 25px;
}

.hero h1 {
    font-size: 48px;
    margin-bottom: 5px;
}

.hero p {
    font-size: 20px;
    color: #cbd5e1;
}

.match-card {
    padding: 22px;
    border-radius: 18px;
    border: 1px solid #334155;
    margin-bottom: 18px;
}

.reciprocal {
    padding: 12px;
    border-radius: 10px;
    background: #064e3b;
    color: #6ee7b7;
    font-weight: 700;
    margin-top: 12px;
}

.badge {
    padding: 5px 10px;
    border-radius: 20px;
    font-size: 13px;
}

.small-text {
    color: #94a3b8;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown(
    "# 🔄 SkillSwap"
)

st.sidebar.caption(
    "Exchange Skills. Grow Together."
)

if not st.session_state.logged_in:

    page = st.sidebar.radio(
        "Navigation",
        [
            "🏠 Home",
            "🔐 Login",
            "📝 Register"
        ]
    )

else:

    user = get_user(
        st.session_state.user_id
    )

    notifications = unread_count(
        st.session_state.user_id
    )

    page = st.sidebar.radio(
        "Navigation",
        [
            "🏠 Dashboard",
            "👤 My Profile",
            "🔎 Find Matches",
            f"📩 Requests ({notifications})",
            "🤝 My Exchanges",
            "🎓 Skill Passport",
            "🔔 Notifications"
        ]
    )

    st.sidebar.divider()

    st.sidebar.write(
        f"👤 **{user[1]}**"
    )

    if st.sidebar.button(
        "🚪 Logout",
        use_container_width=True
    ):

        st.session_state.logged_in = False
        st.session_state.user_id = None

        st.rerun()


# ============================================================
# HOME
# ============================================================

if page == "🏠 Home":

    st.markdown("""
    <div class="hero">

    <h1>🔄 SkillSwap</h1>

    <p>
    Exchange the skills you have.
    Learn the skills you want.
    </p>

    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "🤝 Model",
            "Skill Exchange"
        )

    with c2:

        st.metric(
            "🤖 Matching",
            "Smart AI-style"
        )

    with c3:

        st.metric(
            "🌍 SDG",
            "SDG 8"
        )

    st.divider()

    st.header(
        "How SkillSwap Works"
    )

    cols = st.columns(4)

    process = [
        (
            "1️⃣",
            "Build Profile",
            "Add skills you can teach and skills you want to learn."
        ),
        (
            "2️⃣",
            "Get Matched",
            "Our matching engine finds compatible learners."
        ),
        (
            "3️⃣",
            "Exchange",
            "Connect, schedule and exchange skills."
        ),
        (
            "4️⃣",
            "Grow",
            "Complete exchanges and build your Skill Passport."
        )
    ]

    for col, item in zip(
        cols,
        process
    ):

        with col:

            st.subheader(
                f"{item[0]} {item[1]}"
            )

            st.write(
                item[2]
            )

    st.divider()

    st.info("""
    💡 **Example**

    You can teach **Python** but want to learn **Canva**.

    Another student can teach **Canva** but wants to learn
    **Python**.

    SkillSwap detects this as a **reciprocal match**.
    """)


# ============================================================
# REGISTER
# ============================================================

elif page == "📝 Register":

    st.title(
        "📝 Create Your SkillSwap Account"
    )

    st.caption(
        "Start building your skill network."
    )

    with st.form(
        "register_form"
    ):

        name = st.text_input(
            "Full Name"
        )

        email = st.text_input(
            "Email"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        confirm = st.text_input(
            "Confirm Password",
            type="password"
        )

        submit = st.form_submit_button(
            "🚀 Create Account",
            use_container_width=True
        )

    if submit:

        if not name or not email or not password:

            st.error(
                "Please complete all fields."
            )

        elif password != confirm:

            st.error(
                "Passwords do not match."
            )

        elif len(password) < 6:

            st.error(
                "Password must contain at least 6 characters."
            )

        elif create_user(
            name,
            email,
            password
        ):

            st.success(
                "🎉 Account created successfully!"
            )

            st.info(
                "Go to Login to continue."
            )

        else:

            st.error(
                "An account with this email already exists."
            )


# ============================================================
# LOGIN
# ============================================================

elif page == "🔐 Login":

    st.title(
        "🔐 Welcome Back"
    )

    email = st.text_input(
        "Email"
    )

    password = st.text_input(
        "Password",
        type="password"
    )

    if st.button(
        "Login",
        use_container_width=True
    ):

        user = login_user(
            email,
            password
        )

        if user:

            st.session_state.logged_in = True
            st.session_state.user_id = user[0]

            st.success(
                f"Welcome back, {user[1]}! 👋"
            )

            st.rerun()

        else:

            st.error(
                "Invalid email or password."
            )


# ============================================================
# DASHBOARD
# ============================================================

elif page == "🏠 Dashboard":

    user_id = st.session_state.user_id

    user = get_user(user_id)

    total_skills, active, completed, rating = (
        get_statistics(user_id)
    )

    st.title(
        f"Welcome back, {user[1]} 👋"
    )

    st.caption(
        "Your SkillSwap activity at a glance."
    )

    st.divider()

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "🎯 Skills",
            total_skills
        )

    with c2:

        st.metric(
            "🤝 Active",
            active
        )

    with c3:

        st.metric(
            "✅ Completed",
            completed
        )

    with c4:

        st.metric(
            "⭐ Rating",
            rating if rating else "New"
        )

    st.divider()

    teach = get_skills(
        user_id,
        "teach"
    )

    learn = get_skills(
        user_id,
        "learn"
    )

    c1, c2 = st.columns(2)

    with c1:

        st.subheader(
            "🟢 Skills I Can Teach"
        )

        if teach:

            for skill, level in teach:

                st.write(
                    f"**{skill}** · {level}"
                )

        else:

            st.info(
                "Add your teaching skills."
            )

    with c2:

        st.subheader(
            "🔵 Skills I Want To Learn"
        )

        if learn:

            for skill, level in learn:

                st.write(
                    f"**{skill}** · {level}"
                )

        else:

            st.info(
                "Add your learning goals."
            )

    st.divider()

    st.subheader(
        "🚀 Your Next Step"
    )

    if not teach or not learn:

        st.warning(
            "Complete your profile to unlock smart matching."
        )

    else:

        st.success(
            "Your profile is ready! Go to **Find Matches** "
            "to discover compatible learners."
        )


# ============================================================
# PROFILE
# ============================================================

elif page == "👤 My Profile":

    user_id = st.session_state.user_id

    user = get_user(user_id)

    st.title(
        "👤 My Profile"
    )

    with st.form(
        "profile_form"
    ):

        bio = st.text_area(
            "About Me",
            value=user[4],
            placeholder="Tell others a little about yourself..."
        )

        availability_options = [
            "Morning",
            "Afternoon",
            "Evening",
            "Flexible"
        ]

        availability = st.selectbox(
            "Availability",
            availability_options,
            index=availability_options.index(
                user[5]
            )
            if user[5] in availability_options
            else 3
        )

        mode_options = [
            "Online",
            "Offline",
            "Both"
        ]

        mode = st.selectbox(
            "Preferred Mode",
            mode_options,
            index=mode_options.index(
                user[6]
            )
            if user[6] in mode_options
            else 0
        )

        save = st.form_submit_button(
            "💾 Save Profile"
        )

    if save:

        update_profile(
            user_id,
            bio,
            availability,
            mode
        )

        st.success(
            "Profile updated successfully! ✅"
        )

    st.divider()

    # TEACHING
    st.header(
        "🟢 Skills I Can Teach"
    )

    c1, c2 = st.columns(2)

    with c1:

        teach_name = st.text_input(
            "Skill name",
            key="teach_skill"
        )

    with c2:

        teach_level = st.selectbox(
            "Skill level",
            [
                "Beginner",
                "Intermediate",
                "Advanced"
            ],
            key="teach_level"
        )

    if st.button(
        "➕ Add Teaching Skill"
    ):

        if add_skill(
            user_id,
            teach_name,
            "teach",
            teach_level
        ):

            st.success(
                "Teaching skill added!"
            )

            st.rerun()

        else:

            st.warning(
                "Enter a new skill."
            )

    teaching = get_skills(
        user_id,
        "teach"
    )

    for skill, level in teaching:

        c1, c2, c3 = st.columns(
            [5, 2, 1]
        )

        with c1:

            st.write(
                f"🟢 **{skill}**"
            )

        with c2:

            st.caption(
                level
            )

        with c3:

            if st.button(
                "🗑️",
                key=f"dt_{skill}"
            ):

                delete_skill(
                    user_id,
                    skill,
                    "teach"
                )

                st.rerun()

    st.divider()

    # LEARNING
    st.header(
        "🔵 Skills I Want To Learn"
    )

    c1, c2 = st.columns(2)

    with c1:

        learn_name = st.text_input(
            "Skill name",
            key="learn_skill"
        )

    with c2:

        learn_level = st.selectbox(
            "Current level",
            [
                "Beginner",
                "Intermediate",
                "Advanced"
            ],
            key="learn_level"
        )

    if st.button(
        "➕ Add Learning Goal"
    ):

        if add_skill(
            user_id,
            learn_name,
            "learn",
            learn_level
        ):

            st.success(
                "Learning goal added!"
            )

            st.rerun()

        else:

            st.warning(
                "Enter a new skill."
            )

    learning = get_skills(
        user_id,
        "learn"
    )

    for skill, level in learning:

        c1, c2, c3 = st.columns(
            [5, 2, 1]
        )

        with c1:

            st.write(
                f"🔵 **{skill}**"
            )

        with c2:

            st.caption(
                level
            )

        with c3:

            if st.button(
                "🗑️",
                key=f"dl_{skill}"
            ):

                delete_skill(
                    user_id,
                    skill,
                    "learn"
                )

                st.rerun()


# ============================================================
# FIND MATCHES
# ============================================================

elif page == "🔎 Find Matches":

    user_id = st.session_state.user_id

    st.title(
        "🔎 Smart Skill Matching"
    )

    st.caption(
        "Find people whose skills complement your own."
    )

    search = st.text_input(
        "🔍 Search by name or skill"
    )

    min_score = st.slider(
        "Minimum match score",
        0,
        100,
        0,
        5
    )

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            name,
            bio,
            availability,
            mode
        FROM users

        WHERE id != ?
    """, (user_id,))

    users = cur.fetchall()

    conn.close()

    matches = []

    for other in users:

        result = calculate_match(
            user_id,
            other[0]
        )

        if result["score"] >= min_score:

            matches.append(
                (
                    result,
                    other
                )
            )

    matches.sort(
        key=lambda x: x[0]["score"],
        reverse=True
    )

    if search:

        query = search.lower()

        filtered = []

        for result, other in matches:

            other_skills = (
                get_skills(
                    other[0],
                    "teach"
                )
                +
                get_skills(
                    other[0],
                    "learn"
                )
            )

            skill_names = [
                x[0].lower()
                for x in other_skills
            ]

            if (
                query in other[1].lower()
                or any(
                    query in skill
                    for skill in skill_names
                )
            ):

                filtered.append(
                    (
                        result,
                        other
                    )
                )

        matches = filtered

    st.write(
        f"**{len(matches)} compatible matches found**"
    )

    st.divider()

    if not matches:

        st.info(
            "No compatible matches found. "
            "Try adding more skills to your profile."
        )

    for result, other in matches:

        score = result["score"]

        st.markdown(
            '<div class="match-card">',
            unsafe_allow_html=True
        )

        c1, c2 = st.columns(
            [5, 1]
        )

        with c1:

            st.subheader(
                f"👤 {other[1]}"
            )

            if other[2]:

                st.caption(
                    other[2]
                )

            if result["can_learn"]:

                st.write(
                    "🎓 **They can teach you:** "
                    +
                    ", ".join(
                        sorted(
                            result["can_learn"]
                        )
                    )
                )

            if result["can_teach"]:

                st.write(
                    "💡 **You can teach them:** "
                    +
                    ", ".join(
                        sorted(
                            result["can_teach"]
                        )
                    )
                )

            st.caption(
                f"🕒 {other[3]}   •   💻 {other[4]}"
            )

        with c2:

            st.metric(
                "Match",
                f"{score}%"
            )

        if result["reciprocal"]:

            st.markdown(
                '<div class="reciprocal">'
                '🔄 PERFECT RECIPROCAL MATCH'
                '</div>',
                unsafe_allow_html=True
            )

        with st.expander(
            "🧠 Why this match?"
        ):

            for reason in result["reasons"]:

                st.write(
                    "✓ " + reason
                )

        if st.button(
            "🤝 Send Exchange Request",
            key=f"connect_{other[0]}"
        ):

            if send_request(
                user_id,
                other[0],
                "Hi! I'd like to exchange skills with you."
            ):

                st.success(
                    "Exchange request sent! 📩"
                )

            else:

                st.warning(
                    "You already have a pending request with this user."
                )

        st.markdown(
            "</div>",
            unsafe_allow_html=True
        )


# ============================================================
# REQUESTS
# ============================================================

elif page.startswith(
    "📩 Requests"
):

    user_id = st.session_state.user_id

    st.title(
        "📩 Exchange Requests"
    )

    tab1, tab2 = st.tabs(
        [
            "📥 Incoming",
            "📤 Sent"
        ]
    )

    with tab1:

        incoming = incoming_requests(
            user_id
        )

        if not incoming:

            st.info(
                "No incoming requests yet."
            )

        for item in incoming:

            (
                request_id,
                sender_id,
                name,
                email,
                message,
                status,
                created
            ) = item

            with st.container(
                border=True
            ):

                st.subheader(
                    f"👤 {name}"
                )

                st.write(
                    message
                )

                st.caption(
                    created
                )

                if status == "Pending":

                    c1, c2 = st.columns(2)

                    with c1:

                        if st.button(
                            "✅ Accept",
                            key=f"accept_{request_id}"
                        ):

                            accept_request(
                                request_id
                            )

                            st.success(
                                "Exchange accepted! 🤝"
                            )

                            st.rerun()

                    with c2:

                        if st.button(
                            "❌ Decline",
                            key=f"reject_{request_id}"
                        ):

                            reject_request(
                                request_id
                            )

                            st.rerun()

                else:

                    st.info(
                        f"Status: **{status}**"
                    )

    with tab2:

        sent = sent_requests(
            user_id
        )

        if not sent:

            st.info(
                "You haven't sent any requests."
            )

        for item in sent:

            request_id, name, status, created = item

            st.write(
                f"👤 **{name}** — "
                f"**{status}**"
            )

            st.caption(
                created
            )


# ============================================================
# MY EXCHANGES
# ============================================================

elif page == "🤝 My Exchanges":

    user_id = st.session_state.user_id

    st.title(
        "🤝 My Skill Exchanges"
    )

    exchanges = get_exchanges(
        user_id
    )

    if not exchanges:

        st.info(
            "You don't have any active exchanges yet."
        )

    for exchange in exchanges:

        (
            exchange_id,
            user1,
            user2,
            skill1,
            skill2,
            date,
            time,
            status,
            partner
        ) = exchange

        with st.container(
            border=True
        ):

            st.subheader(
                f"🤝 Exchange with {partner}"
            )

            st.write(
                f"Status: **{status}**"
            )

            if date:

                st.write(
                    f"📅 {date}   🕒 {time}"
                )

            if status == "Active":

                st.markdown(
                    "### 📅 Schedule Exchange"
                )

                date_value = st.date_input(
                    "Date",
                    key=f"date_{exchange_id}"
                )

                time_value = st.time_input(
                    "Time",
                    key=f"time_{exchange_id}"
                )

                if st.button(
                    "📅 Schedule",
                    key=f"schedule_{exchange_id}"
                ):

                    schedule_exchange(
                        exchange_id,
                        str(date_value),
                        str(time_value)
                    )

                    st.success(
                        "Exchange scheduled! 📅"
                    )

                    st.rerun()

                if st.button(
                    "✅ Mark Exchange Completed",
                    key=f"complete_{exchange_id}"
                ):

                    complete_exchange(
                        exchange_id
                    )

                    st.success(
                        "Exchange completed! 🎉"
                    )

                    st.rerun()

            elif status == "Completed":

                st.success(
                    "🎉 Exchange completed."
                )

                partner_user = get_user(
                    user2
                    if user1 == user_id
                    else user1
                )

                if not has_rated(
                    exchange_id,
                    user_id
                ):

                    st.subheader(
                        "⭐ Rate your exchange partner"
                    )

                    rating = st.slider(
                        "Rating",
                        1,
                        5,
                        5,
                        key=f"rating_{exchange_id}"
                    )

                    comment = st.text_area(
                        "Comment",
                        key=f"comment_{exchange_id}",
                        placeholder="How was your experience?"
                    )

                    if st.button(
                        "⭐ Submit Rating",
                        key=f"rate_{exchange_id}"
                    ):

                        submit_rating(
                            exchange_id,
                            user_id,
                            partner_user[0],
                            rating,
                            comment
                        )

                        st.success(
                            "Thank you for your feedback! ⭐"
                        )

                        st.rerun()


# ============================================================
# SKILL PASSPORT
# ============================================================

elif page == "🎓 Skill Passport":

    user_id = st.session_state.user_id

    user = get_user(
        user_id
    )

    total_skills, active, completed, rating = (
        get_statistics(user_id)
    )

    st.title(
        "🎓 Skill Passport"
    )

    st.markdown(
        f"""
        ### {user[1]}

        **{user[4] if user[4] else "SkillSwap learner and contributor"}**
        """
    )

    st.divider()

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "🎯 Skills",
            total_skills
        )

    with c2:

        st.metric(
            "🤝 Exchanges",
            active + completed
        )

    with c3:

        st.metric(
            "✅ Completed",
            completed
        )

    with c4:

        st.metric(
            "⭐ Rating",
            rating if rating else "New"
        )

    st.divider()

    c1, c2 = st.columns(2)

    with c1:

        st.header(
            "🟢 Teaching Skills"
        )

        teaching = get_skills(
            user_id,
            "teach"
        )

        if teaching:

            for skill, level in teaching:

                st.write(
                    f"**{skill}**"
                )

                progress = {
                    "Beginner": 0.33,
                    "Intermediate": 0.66,
                    "Advanced": 1.0
                }[level]

                st.progress(
                    progress
                )

                st.caption(
                    level
                )

        else:

            st.info(
                "No teaching skills yet."
            )

    with c2:

        st.header(
            "🔵 Learning Goals"
        )

        learning = get_skills(
            user_id,
            "learn"
        )

        if learning:

            for skill, level in learning:

                st.write(
                    f"**{skill}**"
                )

                progress = {
                    "Beginner": 0.33,
                    "Intermediate": 0.66,
                    "Advanced": 1.0
                }[level]

                st.progress(
                    progress
                )

                st.caption(
                    level
                )

        else:

            st.info(
                "No learning goals yet."
            )

    st.divider()

    st.subheader(
        "🏆 Achievements"
    )

    if total_skills >= 2:

        st.success(
            "🏆 Skill Builder — Added multiple skills"
        )

    if active + completed >= 1:

        st.success(
            "🤝 Connector — Started a skill exchange"
        )

    if completed >= 1:

        st.success(
            "🎓 Skill Sharer — Completed an exchange"
        )

    if rating >= 4:

        st.success(
            "⭐ Trusted Contributor — Strong community rating"
        )

    if (
        total_skills < 2
        and active + completed == 0
    ):

        st.info(
            "Complete your first exchange to unlock achievements."
        )


# ============================================================
# NOTIFICATIONS
# ============================================================

elif page == "🔔 Notifications":

    user_id = st.session_state.user_id

    st.title(
        "🔔 Notifications"
    )

    notifications = get_notifications(
        user_id
    )

    if not notifications:

        st.info(
            "You're all caught up! 🎉"
        )

    for notification in notifications:

        (
            notification_id,
            title,
            message,
            is_read,
            created
        ) = notification

        if is_read:

            st.caption(
                f"✓ {title} — {created}"
            )

        else:

            with st.container(
                border=True
            ):

                st.subheader(
                    title
                )

                st.write(
                    message
                )

                st.caption(
                    created
                )

    if notifications:

        if st.button(
            "✓ Mark all as read"
        ):

            mark_notifications_read(
                user_id
            )

            st.success(
                "Notifications marked as read."
            )

            st.rerun()