# ============================================================
# PASTE THESE ROUTES INTO /var/www/contractor_app/app.py
# Add before the  if __name__ == '__main__':  line at bottom
# Requires: requests, make_response already imported in Flask
# ============================================================


# ── Craigslist CORS proxy ────────────────────────────────────
@app.route('/api/proxy-fetch', methods=['GET'])
def proxy_fetch():
    if not verify_agent(request):
        return jsonify({'error': 'Unauthorized'}), 401
    url = request.args.get('url', '')
    if not url:
        return jsonify({'error': 'Missing url'}), 400
    if 'craigslist.org' not in url:
        return jsonify({'error': 'Only craigslist.org allowed'}), 403
    try:
        r = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
        resp = make_response(r.text)
        resp.headers['Content-Type'] = r.headers.get('Content-Type', 'text/xml')
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Direct batch lead submission (standalone agents) ─────────
@app.route('/api/leads/submit-batch', methods=['POST'])
def submit_leads_batch():
    if not verify_agent(request):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json() or {}
    source   = data.get('source', 'craigslist')
    keyword  = data.get('keyword', '')
    location = data.get('location', '')
    leads_added = 0
    for result in data.get('results', []):
        url = result.get('url', '')
        if url and Lead.query.filter_by(source_url=url).first():
            continue  # deduplicate
        lead = Lead(
            source=source,
            keyword=keyword,
            location=location,
            title=result.get('title'),
            description=result.get('description'),
            post_text=result.get('post_text'),
            source_url=url,
            posted_at=result.get('posted_at'),
        )
        db.session.add(lead)
        leads_added += 1
    db.session.commit()
    log.info(f"submit-batch: {leads_added} new leads from {source}")
    return jsonify({'success': True, 'leads_added': leads_added})


# ── Contractor signup (form posts here) ──────────────────────
@app.route('/contractor/signup', methods=['GET', 'POST'])
def contractor_signup():
    if request.method == 'GET':
        return render_template('contractor_signup.html')

    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({'success': False, 'error': 'Email required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'error': 'Email already registered'}), 400

    import secrets
    temp_password = secrets.token_hex(8)
    user = User(
        email=email,
        name=data.get('name', '').strip(),
        role='contractor',
    )
    # Store extra fields in metadata if User model doesn't have them as columns
    # If your User model has these columns, uncomment:
    # user.company_name = data.get('company_name', '')
    # user.phone        = data.get('phone', '')
    # user.trade        = data.get('trade', '')
    # user.territory    = data.get('territory', '')
    user.set_password(temp_password)
    db.session.add(user)
    db.session.commit()

    log.info(f"New contractor signup: {email} — trade: {data.get('trade')}")
    return jsonify({'success': True, 'user_id': user.id})
