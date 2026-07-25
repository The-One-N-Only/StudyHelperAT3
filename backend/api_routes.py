import concurrent.futures
import json
import logging
import os
import re
import secrets
import uuid
import flask
from flask import Blueprint, request, jsonify, session, send_file, Response
import src.answer as answer
import src.citations as citations
import src.db as db
import src.embeddings as embeddings
import src.files as files
import src.proxy as proxy
import src.pubmed as pubmed
import src.search as search
import src.semantic_scholar as semantic_scholar
import src.summarise as summarise
from backend.config import BROWSE_SERVER_TIMEOUT_SECONDS
from backend.decorators import require_workspace_role
from src.ratelimit import user_rate_limit, ip_rate_limit
from src.tasks import task_queue, generate_task_id, Task, TaskPriority
import src.english as english
import src.mathematics as mathematics
import src.austlii as austlii
import src.abs_data as abs_data
import src.rba_data as rba_data
import src.gallery_search as gallery_search
import src.aiatsis as aiatsis
import src.tas as tas
import src.dashboard as dashboard

api_bp = Blueprint('api', __name__)


@api_bp.route('/browse/search', methods=['POST'])
@ip_rate_limit(15, 60)
def browse_search():
    data = request.json
    query = data['query']
    source = data.get('source')
    sources = data.get('sources')
    num_results = data['num_results']
    filters = data.get('filters', {})
    user_id = session.get('user_id')

    # Apply enhanced filter parameters
    date_from = filters.get('date_from', '')
    date_to = filters.get('date_to', '')
    source_types = filters.get('source_types', [])
    reading_level = filters.get('reading_level', '')
    if date_from:
        filters['min_date'] = date_from[:4] if len(date_from) >= 4 else date_from
    if date_to:
        filters['max_date'] = date_to[:4] if len(date_to) >= 4 else date_to

    if not search.SERP_API_KEY:
        return jsonify({
            'status': False,
            'error': 'Browse search is not configured. Add SERP_API_KEY and restart StudyLib.'
        }), 503

    requested_sources = [source] if source else list(dict.fromkeys(sources or []))
    results = []
    try:
        for requested_source in requested_sources:
            if requested_source == 'wikipedia':
                results.extend(search.wikipedia(query, num_results, user_id=user_id))
            elif requested_source == 'semantic_scholar':
                results.extend(search.semantic_scholar(query, num_results, user_id=user_id))
            elif requested_source == 'openstax':
                results.extend(search.oer_search(query, num_results, user_id=user_id))
            elif requested_source == 'austlii':
                results.extend(austlii.search_cases(query))
            elif requested_source == 'aiatsis':
                results.extend(aiatsis.search_catalogue(query))
            elif requested_source == 'art_gallery':
                results.extend(gallery_search.search_nga(query) + gallery_search.search_ngv(query))
            else:
                results.extend(search.browse_serpapi_search(
                    query,
                    num_results,
                    requested_source,
                    filters,
                    user_id=user_id,
                ))
    except search.SerpApiProviderError:
        return jsonify({
            'status': False,
            'error': 'Browse search could not reach SerpAPI. Try again shortly.'
        }), 502

    logging.info(f"User {user_id} searched for '{query}' on sources: {requested_sources}")

    return jsonify({'status': True, 'results': results})


@api_bp.route('/browse/search-all', methods=['POST'])
def browse_search_all():
    data = request.json
    query = data['query']
    num_results = data.get('num_results', 20)
    sources = data.get('sources', ['wikipedia', 'gbooks', 'britannica'])
    filters = data.get('filters', {})
    user_id = session.get('user_id')

    # Apply enhanced filter parameters
    date_from = filters.get('date_from', '')
    date_to = filters.get('date_to', '')
    if date_from:
        filters['min_date'] = date_from[:4] if len(date_from) >= 4 else date_from
    if date_to:
        filters['max_date'] = date_to[:4] if len(date_to) >= 4 else date_to

    if not query or not sources:
        return jsonify({'status': False, 'error': 'Query and sources required'}), 400

    independent_sources = {'austlii', 'aiatsis', 'art_gallery'}
    needs_serp = any(s not in independent_sources for s in sources)

    if needs_serp and not search.SERP_API_KEY:
        return jsonify({
            'status': False,
            'error': 'Browse search is not configured. Add SERP_API_KEY and restart StudyLib.'
        }), 503

    requested_sources = []
    seen_sources = set()
    for source in sources:
        if source in seen_sources:
            continue
        seen_sources.add(source)
        requested_sources.append(source)

    if any(source.startswith('whitelist_') for source in requested_sources):
        requested_sources = [
            source for source in requested_sources if source != 'whitelist'
        ]

    selected_sources = set(requested_sources)
    dedicated_source_by_domain = {
        domain: source
        for source, (domain, _source_name) in search.BROWSE_SOURCE_DOMAINS.items()
    }
    requested_sources = [
        source
        for source in requested_sources
        if not (
            source.startswith('whitelist_')
            and dedicated_source_by_domain.get(source.split('_', 1)[1])
            in selected_sources
        )
    ]

    grouped_results = {}
    source_counts = {}
    source_errors = {}

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
    futures = {}
    for source in requested_sources:
        if source == 'wikipedia':
            futures[source] = executor.submit(
                search.wikipedia,
                query,
                num_results,
                user_id=user_id,
            )
        elif source == 'semantic_scholar':
            futures[source] = executor.submit(
                search.semantic_scholar,
                query,
                num_results,
                user_id=user_id,
            )
        elif source == 'openstax':
            futures[source] = executor.submit(
                search.oer_search,
                query,
                num_results,
                user_id=user_id,
            )
        elif source == 'austlii':
            futures[source] = executor.submit(austlii.search_cases, query)
        elif source == 'aiatsis':
            futures[source] = executor.submit(aiatsis.search_catalogue, query)
        elif source == 'art_gallery':
            futures[source] = executor.submit(
                lambda: gallery_search.search_nga(query) + gallery_search.search_ngv(query)
            )
        else:
            futures[source] = executor.submit(
                search.browse_serpapi_search,
                query,
                num_results,
                source,
                filters,
                user_id=user_id,
            )
    try:
        done, not_done = concurrent.futures.wait(
            futures.values(),
            timeout=BROWSE_SERVER_TIMEOUT_SECONDS,
        )
        for source, future in futures.items():
            if future in not_done:
                future.cancel()
                logging.warning("SerpAPI Browse search timed out for source %s", source)
                source_errors[source] = 'Search timed out'
                grouped_results[source] = []
                source_counts[source] = 0
                continue
            try:
                source_results = future.result() or []
                grouped_results[source] = source_results
                source_counts[source] = len(source_results)
            except search.SerpApiProviderError:
                source_errors[source] = 'SerpAPI search failed'
                grouped_results[source] = []
                source_counts[source] = 0
            except Exception:
                logging.exception("Browse search failed for source %s", source)
                source_errors[source] = 'Search failed'
                grouped_results[source] = []
                source_counts[source] = 0
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if futures and len(source_errors) == len(futures):
        return jsonify({
            'status': False,
            'error': 'Browse search could not reach SerpAPI. Try again shortly.',
            'source_errors': source_errors,
        }), 502

    flattened = [
        (source, item)
        for source, items in grouped_results.items()
        for item in items
    ]
    unique_items = iter(search.deduplicate_results([item for _, item in flattened]))
    next_unique = next(unique_items, None)
    deduplicated_groups = {source: [] for source in grouped_results}
    all_results = []
    for source, item in flattened:
        if item is not next_unique:
            continue
        response_item = search.with_response_dedupe_metadata(item)
        deduplicated_groups[source].append(response_item)
        all_results.append(response_item)
        next_unique = next(unique_items, None)

    logging.info(
        f"User {user_id} performed multi-source search for '{query}' "
        f"across {len(futures)} sources"
    )

    return jsonify({
        'status': True,
        'results': all_results,
        'grouped_results': deduplicated_groups,
        'source_counts': source_counts,
        'source_errors': source_errors,
    })


@api_bp.route('/browse/summary', methods=['POST'])
def browse_summary():
    data = request.json
    query = data.get('query', '').strip()
    results = data.get('results', [])
    atn = data.get('atn')
    user_id = session.get('user_id')

    if not query:
        return jsonify({'status': False, 'error': 'Query required'}), 400

    try:
        summary = summarise.summarise_search_results(query, results, atn)
        logging.info(f"User {user_id} requested search summary for '{query}'")
        return jsonify(summary)
    except Exception as e:
        logging.error(f"Search summary failed for user {user_id}: {str(e)}")
        return jsonify({'status': False, 'error': 'Search summarisation failed'}), 500


@api_bp.route('/filters')
def api_filters():
    return send_file(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'filters.json'), mimetype='application/json')


@api_bp.route('/parse-boolean-query', methods=['POST'])
def parse_boolean_query():
    data = request.json
    raw_query = (data.get('query', '') or '').strip()
    if not raw_query:
        return jsonify({'status': False, 'error': 'Query required'}), 400

    tokens = re.findall(r'"[^"]*"|\S+', raw_query)
    result = _parse_boolean_or(tokens, 0)
    parsed, _ = result if result else (raw_query, len(tokens))
    return jsonify({'status': True, 'parsed': parsed, 'original': raw_query})


def _parse_boolean_or(tokens, pos):
    left, pos = _parse_boolean_and(tokens, pos)
    while pos < len(tokens) and tokens[pos].upper() == 'OR':
        pos += 1
        right, pos = _parse_boolean_and(tokens, pos)
        left = {'type': 'or', 'left': left, 'right': right}
    return left, pos


def _parse_boolean_and(tokens, pos):
    left, pos = _parse_boolean_not(tokens, pos)
    while pos < len(tokens) and tokens[pos].upper() == 'AND':
        pos += 1
        right, pos = _parse_boolean_not(tokens, pos)
        left = {'type': 'and', 'left': left, 'right': right}
    return left, pos


def _parse_boolean_not(tokens, pos):
    if pos < len(tokens) and tokens[pos].upper() == 'NOT':
        pos += 1
        operand, pos = _parse_boolean_primary(tokens, pos)
        return {'type': 'not', 'operand': operand}, pos
    return _parse_boolean_primary(tokens, pos)


def _parse_boolean_primary(tokens, pos):
    if pos >= len(tokens):
        return '', pos
    token = tokens[pos]
    if token.startswith('"') and token.endswith('"'):
        pos += 1
        return token[1:-1], pos
    pos += 1
    return token, pos


@api_bp.route('/pubmed/mesh-suggestions')
def pubmed_mesh_suggestions():
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify({'status': False, 'error': 'Query too short'}), 400

    terms = pubmed.get_mesh_terms(query, num_results=10)
    logging.info(f"User {session.get('user_id', 'anonymous')} requested MeSH suggestions for '{query}'")
    return jsonify({'status': True, 'suggestions': terms})


@api_bp.route('/proxy/source')
def proxy_source():
    url = request.args.get('url')
    user_id = session.get('user_id')
    if not url:
        return jsonify({'status': False, 'error': 'No URL'}), 400
    try:
        result = proxy.fetch_source(url)
        logging.info(f"User {user_id} proxied source for {url}")
        return jsonify(result)
    except ValueError:
        return jsonify({'status': False, 'error': 'URL not allowed'}), 403


@api_bp.route('/summarise', methods=['POST'])
@user_rate_limit(10, 60)
def api_summarise():
    data = request.json
    url = data.get('url')
    file_id = data.get('file_id')
    atn = data.get('atn')
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    task_id = generate_task_id()

    def _run_summarisation():
        if url:
            try:
                return summarise.summarise_url(url, data.get('title', ''), atn)
            except ValueError:
                return {'status': False, 'error': 'URL not allowed'}
        elif file_id:
            return summarise.summarise_file(file_id, user_id, atn)
        return {'status': False, 'error': 'No URL or file_id'}

    task = Task(id=task_id, func=_run_summarisation)
    task_queue.enqueue(task)

    logging.info(f"User {user_id} queued AI summary task {task_id} for {url or f'file {file_id}'}")
    return jsonify({'status': 'queued', 'task_id': task_id})


@api_bp.route('/task-status/<task_id>', methods=['GET'])
def task_status(task_id):
    result = task_queue.get_result(task_id)
    if result is None:
        return jsonify({'status': 'pending', 'task_id': task_id})
    return jsonify({'status': 'completed', 'task_id': task_id, 'result': result})


@api_bp.route('/workspace/add', methods=['POST'])
def workspace_add():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    item_id = data.get('item_id')
    summary = data.get('summary')
    bullets = json.dumps(data.get('bullets', []))
    relevance = data.get('relevance')
    atn_used = data.get('atn_used')
    citation_apa = data.get('citation_apa', '')
    citation_harvard = data.get('citation_harvard', '')
    workspace_id = data.get('workspace_id')

    try:
        result = db.add_to_workspace(user_id, item_id, summary, bullets, relevance, atn_used, citation_apa, citation_harvard, workspace_id)
        if result and result.get("duplicate"):
            logging.info(f"User {user_id} tried to add duplicate item {item_id} to workspace {workspace_id or 'default'}")
            return jsonify({'status': True, 'duplicate': True, 'message': 'Already in this workspace'})
        logging.info(f"User {user_id} added item {item_id} to workspace {workspace_id or 'default'}")
        return jsonify({'status': True, 'item': result})
    except Exception as e:
        logging.error(f"Error adding to workspace: {str(e)}")
        return jsonify({'status': False, 'error': 'Failed to add item'}), 500


@api_bp.route('/workspaces/<int:workspace_id>/add-file', methods=['POST'])
def add_file_to_workspace(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    file_id = data.get('file_id')
    if not file_id:
        return jsonify({'status': False, 'error': 'file_id required'}), 400

    try:
        result = db.add_file_to_workspace(user_id, file_id, workspace_id)
        if result and result.get("duplicate"):
            logging.info(f"User {user_id} tried to add duplicate file {file_id} to workspace {workspace_id}")
            return jsonify({'status': True, 'duplicate': True, 'message': 'Already in this workspace'})
        logging.info(f"User {user_id} added file {file_id} to workspace {workspace_id}")
        return jsonify({'status': True, 'item': result})
    except Exception as e:
        logging.error(f"Error adding file to workspace: {str(e)}")
        return jsonify({'status': False, 'error': 'Failed to add file to workspace'}), 500


@api_bp.route('/workspaces', methods=['GET'])
def get_workspaces():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    workspaces = db.get_user_workspaces(user_id)
    return jsonify({'status': True, 'workspaces': workspaces})


@api_bp.route('/workspaces/<int:workspace_id>', methods=['GET'])
def get_workspace(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    workspace = db.get_workspace(user_id, workspace_id)
    if not workspace:
        return jsonify({'status': False, 'error': 'Workspace not found'}), 404

    return jsonify({'status': True, 'workspace': workspace})


@api_bp.route('/workspaces/<int:workspace_id>/chat', methods=['GET'])
def get_workspace_chat(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    workspace = db.get_workspace(user_id, workspace_id)
    if not workspace:
        return jsonify({'status': False, 'error': 'Workspace not found'}), 404

    messages = db.get_workspace_chat_messages(workspace_id, user_id)
    return jsonify({
        'status': True,
        'messages': messages,
        'ai_configured': answer._anthropic_client is not None or answer.FALLBACK_MODE == "local",
    })


@api_bp.route('/workspaces', methods=['POST'])
def create_workspace():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    name = data.get('name', 'New Workspace').strip()[:25]
    if not name:
        return jsonify({'status': False, 'error': 'Workspace name is required'}), 400
    parent_id = data.get('parent_id')
    folder_id = data.get('folder_id')
    course_id = data.get('course_id')
    workspace = db.create_workspace(user_id, name, parent_id=parent_id, folder_id=folder_id, course_id=course_id)
    logging.info(f"User {user_id} created workspace: {name}")
    return jsonify({'status': True, 'workspace': workspace})


@api_bp.route('/workspaces/<int:workspace_id>', methods=['PUT'])
def update_workspace(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'status': False, 'error': 'Name required'}), 400

    workspace = db.rename_workspace(workspace_id, user_id, name)
    if not workspace:
        return jsonify({'status': False, 'error': 'Workspace not found'}), 404

    logging.info(f"User {user_id} renamed workspace {workspace_id} to: {name}")
    return jsonify({'status': True, 'workspace': workspace})


@api_bp.route('/workspaces/<int:workspace_id>', methods=['DELETE'])
def delete_workspace(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    if db.delete_workspace(workspace_id, user_id):
        logging.info(f"User {user_id} deleted workspace {workspace_id}")
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Workspace not found'}), 404


@api_bp.route('/workspaces/<int:workspace_id>/notes', methods=['GET'])
def get_workspace_notes(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    notes = db.get_workspace_notes(workspace_id, user_id)
    return jsonify({'status': True, 'notes': notes})


@api_bp.route('/workspaces/<int:workspace_id>/notes', methods=['POST'])
def create_workspace_note(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    title = data.get('title', 'New Note')
    content = data.get('content', '')

    note = db.create_workspace_note(user_id, workspace_id, title, content)
    logging.info(f"User {user_id} created note in workspace {workspace_id}")
    return jsonify({'status': True, 'note': note})


@api_bp.route('/workspace/<int:item_id>', methods=['DELETE'])
def workspace_remove(item_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    result = db.remove_from_workspace(item_id, user_id)
    if result:
        logging.info(f"User {user_id} removed item {item_id} from workspace")
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Not found'}), 404


@api_bp.route('/workspace/reorder', methods=['POST'])
def workspace_reorder():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    ordered_ids = data['ordered_ids']
    db.reorder_workspace(user_id, ordered_ids)
    logging.info(f"User {user_id} reordered workspace")
    return jsonify({'status': True})


@api_bp.route('/workspace/items')
def workspace_items():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    workspace_id = request.args.get('workspace_id', type=int)
    items = db.get_workspace_items(user_id, workspace_id) or []
    for item in items:
        source_name = (item.get('source_name') or '').lower()
        source_url = item.get('source_url') or ''
        if source_name in ('gbooks', 'google books') or 'books.google.com' in source_url:
            volume_id = search._google_books_volume_id(source_url)
            if not volume_id:
                source_id = item.get('source_id', '')
                volume_id = search._google_books_volume_id(source_id)
            if not volume_id:
                source_id = item.get('source_id', '')
                if isinstance(source_id, str) and search.GOOGLE_BOOKS_VOLUME_ID_PATTERN.fullmatch(source_id):
                    volume_id = source_id
            if volume_id:
                item['google_books_volume_id'] = volume_id
            item['accessInfo'] = {
                'embeddable': True,
                'webReaderLink': source_url,
                'viewability': 'UNKNOWN',
                'accessViewStatus': 'NONE',
            }
    logging.info(f"User {user_id} viewed workspace items for workspace {workspace_id or 'default'}")
    return jsonify({'status': True, 'items': items})


CITATION_STYLES = {
    "apa": {"name": "APA 7th Edition", "description": "American Psychological Association style"},
    "harvard": {"name": "Harvard", "description": "Harvard referencing style"},
    "mla": {"name": "MLA 9th Edition", "description": "Modern Language Association style"},
    "chicago": {"name": "Chicago 17th Edition", "description": "Chicago Manual of Style (notes-bibliography)"},
    "ieee": {"name": "IEEE", "description": "Institute of Electrical and Electronics Engineers style"},
}


@api_bp.route('/citation-styles')
def citation_styles():
    return jsonify({"status": True, "styles": CITATION_STYLES})


@api_bp.route('/export-citations', methods=['POST'])
def export_citations():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    item_ids = data.get('item_ids', [])
    style = data.get('style', 'apa')
    fmt = data.get('format', 'text')

    if style not in CITATION_STYLES:
        return jsonify({'status': False, 'error': f'Unsupported style: {style}'}), 400

    citations_list = []
    for item_id in item_ids:
        item = db.get_item_by_id(item_id, user_id, add_to_recent_search=False)
        if not item:
            continue
        cit = citations.format_citation(
            title=item.get("title", ""),
            source=item.get("source_name", ""),
            url=item.get("source_url", ""),
            style=style,
            author=item.get("authors") or item.get("author"),
            year=item.get("year"),
        )
        citations_list.append(cit)

    if fmt == "json":
        return jsonify({"status": True, "citations": citations_list})
    elif fmt == "csv":
        import io
        import csv as csv_mod
        output = io.StringIO()
        writer = csv_mod.writer(output)
        writer.writerow(["Citation"])
        for c in citations_list:
            writer.writerow([c])
        return jsonify({"status": True, "csv": output.getvalue()})
    else:
        return jsonify({"status": True, "text": "\n".join(citations_list)})


@api_bp.route('/workspace-items/<int:item_id>/citation')
def workspace_item_citation(item_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    items = db.get_workspace_items(user_id)
    item = next((it for it in items if it.get("id") == item_id), None)
    if not item:
        return jsonify({'status': False, 'error': 'Item not found'}), 404

    result = {}
    for style in CITATION_STYLES:
        cit = citations.format_citation(
            title=item.get("title", ""),
            source=item.get("source_name", ""),
            url=item.get("source_url", ""),
            style=style,
            author=item.get("authors") or item.get("author"),
            year=item.get("year"),
        )
        result[style] = cit

    return jsonify({"status": True, "citations": result})


@api_bp.route('/bibliography/sort', methods=['POST'])
def bibliography_sort():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    raw_citations = data.get('citations', [])
    style = data.get('style', 'apa')
    sorted_cit = citations.sort_bibliography(raw_citations, style)
    return jsonify({"status": True, "citations": sorted_cit})


@api_bp.route('/export-templates', methods=['GET'])
def list_export_templates():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    templates = db.get_export_templates(user_id)
    return jsonify({"status": True, "templates": templates})


@api_bp.route('/export-templates', methods=['POST'])
def create_export_template():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    name = data.get('name', '').strip()
    template_content = data.get('template_content', '')
    is_public = data.get('is_public', False)
    if not name:
        return jsonify({'status': False, 'error': 'Name required'}), 400
    tmpl = db.create_export_template(user_id, name, template_content, is_public)
    return jsonify({"status": True, "template": tmpl})


@api_bp.route('/export-templates/<int:template_id>', methods=['PUT'])
def update_export_template(template_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    tmpl = db.update_export_template(template_id, user_id,
                                     name=data.get('name'),
                                     template_content=data.get('template_content'),
                                     is_public=data.get('is_public'))
    if not tmpl:
        return jsonify({'status': False, 'error': 'Not found'}), 404
    return jsonify({"status": True, "template": tmpl})


@api_bp.route('/export-templates/<int:template_id>', methods=['DELETE'])
def delete_export_template_route(template_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    if db.delete_export_template(template_id, user_id):
        return jsonify({"status": True})
    return jsonify({'status': False, 'error': 'Not found'}), 404


@api_bp.route('/export/preview-with-template', methods=['POST'])
def export_preview_with_template():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    content = data.get('content', '')
    template_name = data.get('template_id', 'default')
    metadata = data.get('metadata', {})

    import src.export as export_mod
    rendered = export_mod.apply_export_template(content, str(template_name), metadata)
    return jsonify({"status": True, "content": rendered})


@api_bp.route('/citations/generate', methods=['POST'])
def generate_citations():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    items = data['items']
    format_type = data['format']

    citations_list = []
    for item in items:
        kwargs = dict(
            title=item['title'],
            source_name=item['source_name'],
            url=item['url'],
            author=item.get('author'),
            year=item.get('year'),
            authors=item.get('authors'),
            journal=item.get('journal'),
            volume=item.get('volume'),
            issue=item.get('issue'),
            doi=item.get('doi'),
        )
        if format_type == 'apa':
            cit = citations.format_apa(**kwargs)
        else:
            cit = citations.format_harvard(**kwargs)
        citations_list.append(cit)

    logging.info(f"User {user_id} generated {len(items)} citations in {format_type} format")
    return jsonify({'status': True, 'citations': citations_list})


@api_bp.route('/files/upload', methods=['POST'])
def upload_file():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    file = request.files.get('file')
    if not file:
        return jsonify({'status': False, 'error': 'No file'}), 400

    allowed_mimes = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
        'image/jpeg', 'image/png', 'image/gif', 'image/webp',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'application/x-msexcel',
        'application/x-excel',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'text/csv',
        'application/json'
    ]
    if file.mimetype not in allowed_mimes:
        return jsonify({'status': False, 'error': 'Invalid file type'}), 400

    if file.content_length > 10 * 1024 * 1024:
        return jsonify({'status': False, 'error': 'File too large'}), 400

    if file.mimetype == 'application/pdf':
        file_type = 'pdf'
    elif file.mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        file_type = 'docx'
    elif file.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        file_type = 'xlsx'
    elif file.mimetype in ['application/vnd.ms-excel', 'application/x-msexcel', 'application/x-excel']:
        file_type = 'xls'
    elif file.mimetype.startswith('image/'):
        file_type = 'image'
    elif file.mimetype == 'application/vnd.openxmlformats-officedocument.presentationml.presentation':
        file_type = 'pptx'
    elif file.mimetype == 'text/csv':
        file_type = 'csv'
    elif file.mimetype == 'application/json':
        file_type = 'json'
    else:
        file_type = 'txt'

    filename = f"{uuid.uuid4()}_{file.filename}"
    stored_path = f"static/uploads/{user_id}/{filename}"
    os.makedirs(os.path.dirname(stored_path), exist_ok=True)
    file.save(stored_path)

    file_hash = db.hash_file(stored_path)
    duplicate = db.check_duplicate_file(user_id, file_hash)
    if duplicate:
        override = request.args.get('override', 'false').lower() == 'true'
        if not override:
            return jsonify({
                'status': 'duplicate',
                'existing_file': duplicate,
                'message': f'You already uploaded this file ({duplicate["filename"]})'
            })

    extracted_text = files.extract_text(stored_path, file_type)
    if not extracted_text and file_type in ('pdf', 'image'):
        extracted_text = files.extract_text_ocr(stored_path, file_type)

    result = db.create_uploaded_file(user_id, file.filename, stored_path, file_type, extracted_text, file.content_length, file_hash=file_hash)

    # Store embeddings for semantic search
    try:
        chunks = files.chunk_text(extracted_text)
        if chunks:
            chunk_data = []
            for chunk in chunks:
                vec = embeddings.compute_simple_embedding(chunk)
                chunk_data.append((chunk, vec))
            db.store_file_embeddings(result["id"], chunk_data)
    except Exception:
        logging.exception("Failed to store file embeddings")

    # Store per-page text for PDFs
    try:
        pages = files.extract_text_pages(stored_path, file_type)
        if pages:
            db.store_file_pages(result["id"], [(i+1, p) for i, p in enumerate(pages)])
    except Exception:
        logging.exception("Failed to store file pages")

    logging.info(f"User {user_id} uploaded file {file.filename} ({file_type})")
    return jsonify({'status': True, 'file_id': result['id'], 'filename': result['filename'], 'url': f"/static/uploads/{user_id}/{result['id']}_{result['filename']}"})


@api_bp.route('/files/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    result = db.delete_uploaded_file(file_id, user_id)
    if result:
        files_list = db.get_uploaded_files(user_id)
        file_data = next((f for f in files_list if f['id'] == file_id), None)
        if file_data:
            os.remove(file_data['stored_path'])
        logging.info(f"User {user_id} deleted file {file_id}")
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Not found'}), 404


@api_bp.route('/files/list')
def list_files():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    files_list = db.get_uploaded_files(user_id) or []
    logging.info(f"User {user_id} listed uploaded files")
    return jsonify({'status': True, 'files': files_list})


@api_bp.route('/files/search')
def search_files():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    query = request.args.get('q', '')
    results = db.search_uploaded_files(user_id, query)
    logging.info(f"User {user_id} searched uploaded files for '{query}'")
    return jsonify({'status': True, 'results': results})


@api_bp.route('/item/save', methods=['POST'])
def save_item():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    item_id = data['item_id']
    query = data.get('query', '')
    result = db.save_item(item_id, user_id, query=query)
    logging.info(f"User {user_id} saved item {item_id} with query '{query}'")
    return jsonify({'status': result is not None})


@api_bp.route('/item/unsave', methods=['POST'])
def unsave_item():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    item_id = data['item_id']
    result = db.unsave_item(item_id, user_id)
    logging.info(f"User {user_id} unsaved item {item_id}")
    return jsonify({'status': result is not None})


@api_bp.route('/saved')
def api_saved():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    grouped = db.get_saved_items_grouped(user_id)
    logging.info(f"User {user_id} fetched saved items")
    return jsonify({'status': True, 'groups': grouped})


@api_bp.route('/recent/viewed', methods=['POST'])
def add_recent_viewed():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    item_id = data['item_id']
    db.append_to_recently_viewed(user_id, item_id)
    logging.info(f"User {user_id} added to recently viewed {item_id}")
    return jsonify({'status': True})


@api_bp.route('/answer/prompt', methods=['POST'])
@user_rate_limit(20, 60)
def answer_prompt():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    prompt = data.get('prompt', '').strip()
    search_web = data.get('search_web', True)
    atn = data.get('atn')

    if not prompt:
        return jsonify({'status': False, 'error': 'No prompt provided'}), 400

    result = answer.answer_prompt(prompt, user_id, search_web=search_web, atn=atn)
    logging.info(f"User {user_id} asked prompt: {prompt[:50]}")
    return jsonify(result)


@api_bp.route('/answer/chat', methods=['POST'])
@user_rate_limit(30, 60)
@require_workspace_role('editor', optional=True)
def answer_chat():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.get_json(silent=True) or {}
    messages = data.get('messages', [])
    atn = data.get('atn')
    workspace_id = data.get('workspace_id')
    persona = data.get('persona', 'formal')

    if not messages:
        return jsonify({'status': False, 'error': 'No messages provided'}), 400

    latest_user_content = None
    if workspace_id is not None:
        if isinstance(workspace_id, bool):
            return jsonify({'status': False, 'error': 'Invalid workspace ID'}), 400
        try:
            workspace_id = int(workspace_id)
        except (TypeError, ValueError):
            return jsonify({'status': False, 'error': 'Invalid workspace ID'}), 400

        workspace = db.get_workspace(user_id, workspace_id)
        if not workspace:
            return jsonify({'status': False, 'error': 'Workspace not found'}), 404
        persona = workspace.get('persona', persona)

        latest_user_content = next((
            message.get('content')
            for message in reversed(messages)
            if isinstance(message, dict)
            and message.get('role') == 'user'
            and isinstance(message.get('content'), str)
            and message.get('content').strip()
        ), None)
        if latest_user_content is None:
            return jsonify({'status': False, 'error': 'No user message provided'}), 400

    result = answer.chat_with_sources(messages, user_id, atn=atn, workspace_id=workspace_id, persona=persona)
    if isinstance(result, str):
        result = {'status': True, 'response': result}
    elif not isinstance(result, dict):
        logging.error("AI chat returned an invalid response type for user %s", user_id)
        result = {'status': False, 'error': 'Alexander returned an invalid response.'}

    if workspace_id is not None and result.get('status') is True:
        assistant_content = result.get('response')
        if not isinstance(assistant_content, str) or not assistant_content.strip():
            logging.error("AI chat returned no response text for user %s", user_id)
            return jsonify({
                'status': False,
                'error': 'Alexander returned an invalid response.',
            }), 502
        try:
            persisted = db.append_workspace_chat_turn(
                user_id,
                workspace_id,
                latest_user_content,
                assistant_content,
                citations=result.get('citations'),
            )
        except Exception:
            logging.exception(
                "Failed to persist chat turn for user %s workspace %s",
                user_id,
                workspace_id,
            )
            return jsonify({
                'status': False,
                'error': 'Alexander answered, but the conversation could not be saved.',
            }), 500
        if not persisted:
            return jsonify({'status': False, 'error': 'Workspace not found'}), 404

    logging.info(f"User {user_id} had multi-turn conversation")
    return jsonify(result)


@api_bp.route('/search-history', methods=['GET'])
def api_search_history():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    limit = request.args.get('limit', 20, type=int)
    history = db.get_search_history(user_id, limit=limit)
    return jsonify({'status': True, 'history': history})


@api_bp.route('/search-history', methods=['DELETE'])
def api_clear_search_history():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    db.clear_search_history(user_id)
    return jsonify({'status': True})


@api_bp.route('/search-history/re-run', methods=['POST'])
def api_rerun_search():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    query_id = data.get('query_id')
    if not query_id:
        return jsonify({'status': False, 'error': 'query_id required'}), 400
    entry = db.get_search_history_entry(query_id, user_id)
    if not entry:
        return jsonify({'status': False, 'error': 'Search history entry not found'}), 404
    return jsonify({'status': True, 'entry': entry})


@api_bp.route('/search-history/save', methods=['POST'])
def api_save_search_history():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    query = data.get('query', '')
    source_filters = data.get('source_filters', [])
    num_results = data.get('num_results', 0)
    if not query:
        return jsonify({'status': False, 'error': 'Query required'}), 400
    entry = db.add_search_history(user_id, query, source_filters, num_results)
    return jsonify({'status': True, 'entry': entry})


@api_bp.route('/related-sources')
def api_related_sources():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    item_id = request.args.get('item_id', type=int)
    limit = request.args.get('limit', 5, type=int)
    if not item_id:
        return jsonify({'status': False, 'error': 'item_id required'}), 400
    related = search.get_related_sources(item_id, user_id, limit=limit)
    return jsonify({'status': True, 'related': related})


@api_bp.route('/chat/suggest-questions', methods=['POST'])
def suggest_questions():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    workspace_id = data.get('workspace_id')
    last_response = data.get('last_response', '')

    workspace_context = ""
    if workspace_id:
        items = db.get_workspace_items(user_id, workspace_id) or []
        workspace_context = " ".join([
            f"{i.get('title', '')}: {i.get('summary', '')[:200]}"
            for i in items[:5]
        ])

    history = [{"role": "assistant", "content": last_response}]
    questions = answer.generate_follow_up_questions(history, workspace_context)
    return jsonify({'status': True, 'questions': questions})


# ========== GDPR Data Export ==========

@api_bp.route('/account/export', methods=['POST'])
def export_account_data():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    import io
    import zipfile
    import json as json_mod

    user = db.get_user_by_id(user_id)
    if not user:
        return jsonify({'status': False, 'error': 'User not found'}), 404

    data = export_user_data(user_id)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('user_data.json', json_mod.dumps(data, indent=2, default=str))

        # Include uploaded files
        for f in data.get('uploaded_files', []):
            stored_path = f.get('stored_path', '')
            if stored_path and os.path.exists(stored_path):
                arcname = f"uploads/{f.get('filename', 'file')}"
                zf.write(stored_path, arcname)

    buf.seek(0)
    return send_file(
        buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'studylib-export-user-{user_id}.zip',
    )


def export_user_data(user_id: int) -> dict:
    user = db.get_user_by_id(user_id)
    if not user:
        return {}

    workspaces = db.get_user_workspaces(user_id) or []
    workspace_details = []
    for ws in workspaces:
        items = db.get_workspace_items(user_id, ws['id']) or []
        notes = db.get_workspace_notes(ws['id'], user_id)
        chat = db.get_workspace_chat_messages(ws['id'], user_id)
        workspace_details.append({
            "id": ws['id'],
            "name": ws['name'],
            "time_created": ws.get('time_created'),
            "archived": ws.get('archived', False),
            "items": items,
            "notes": notes,
            "chat_messages": chat,
        })

    search_history = db.get_search_history(user_id) or []

    saved_items = db.get_saved_items(user_id) or []
    uploaded_files = db.get_uploaded_files(user_id) or []

    return {
        "profile": {
            "username": user.username,
            "email": user.email,
            "gender": user.gender,
            "created_at": user.time_created,
        },
        "workspaces": workspace_details,
        "search_history": search_history,
        "saved_items": saved_items,
        "uploaded_files": uploaded_files,
    }


@api_bp.route('/synthesize', methods=['POST'])
def synthesize():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    workspace_id = data.get('workspace_id')
    source_ids = data.get('source_ids', [])
    instruction = data.get('instruction', 'themes')

    items = db.get_workspace_items(user_id, workspace_id) or []
    filtered = [i for i in items if i['id'] in source_ids] if source_ids else items[:5]
    if not filtered:
        return jsonify({'status': False, 'error': 'No sources selected'}), 400

    source_texts = []
    for item in filtered:
        source_texts.append({
            "title": item.get("title", "Untitled"),
            "source": item.get("source_name", ""),
            "content": item.get("abstract") or item.get("summary", ""),
        })

    result = answer.synthesize_sources(source_texts, instruction)
    return jsonify(result)


@api_bp.route('/study-guide', methods=['POST'])
def study_guide():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    workspace_id = data.get('workspace_id')
    if not workspace_id:
        return jsonify({'status': False, 'error': 'workspace_id required'}), 400

    result = answer.generate_study_guide(workspace_id, user_id)
    return jsonify(result)


@api_bp.route('/essay-outline', methods=['POST'])
def essay_outline():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    workspace_id = data.get('workspace_id')
    thesis = data.get('thesis', '').strip()
    if not thesis:
        return jsonify({'status': False, 'error': 'Thesis statement required'}), 400

    result = answer.generate_essay_outline(workspace_id, user_id, thesis)
    return jsonify(result)


@api_bp.route('/suggest-tags', methods=['POST'])
def suggest_tags():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    title = data.get('title', '')
    snippet = data.get('snippet', '')

    tags = summarise.suggest_tags(title, snippet)
    return jsonify({'status': True, 'tags': tags})


# ========== Tag Endpoints ==========

@api_bp.route('/tags', methods=['GET'])
def list_tags():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    tags = db.get_user_tags(user_id)
    return jsonify({'status': True, 'tags': tags})


@api_bp.route('/tags', methods=['POST'])
def create_tag():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    name = data.get('name', '').strip()
    color = data.get('color', '#0d6efd')
    if not name:
        return jsonify({'status': False, 'error': 'Name required'}), 400
    tag = db.create_tag(name, color, user_id)
    return jsonify({'status': True, 'tag': tag})


@api_bp.route('/tags/<int:tag_id>', methods=['DELETE'])
def delete_tag(tag_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    if db.delete_tag(tag_id, user_id):
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Tag not found'}), 404


@api_bp.route('/workspace-items/<int:item_id>/tags', methods=['POST'])
def add_item_tag(item_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    tag_id = data.get('tag_id')
    if not tag_id:
        return jsonify({'status': False, 'error': 'tag_id required'}), 400
    result = db.add_tag_to_workspace_item(item_id, tag_id)
    if result:
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Already tagged or not found'}), 400


@api_bp.route('/workspace-items/<int:item_id>/tags/<int:tag_id>', methods=['DELETE'])
def remove_item_tag(item_id, tag_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    if db.remove_tag_from_workspace_item(item_id, tag_id):
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Tag not found on item'}), 404


@api_bp.route('/workspace/<int:workspace_id>/items-by-tag')
def items_by_tag(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    tag_id = request.args.get('tag_id', type=int)
    if not tag_id:
        return jsonify({'status': False, 'error': 'tag_id required'}), 400
    items = db.get_workspace_items_by_tag(tag_id, workspace_id, user_id)
    return jsonify({'status': True, 'items': items})


# ========== Bulk Action Endpoints ==========

@api_bp.route('/workspace-items/bulk-move', methods=['POST'])
def bulk_move_items():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    item_ids = data.get('item_ids', [])
    target_workspace_id = data.get('target_workspace_id')
    if not item_ids or not target_workspace_id:
        return jsonify({'status': False, 'error': 'item_ids and target_workspace_id required'}), 400
    with db.SessionLocal() as session:
        for wid in item_ids:
            wi = session.query(db.WorkspaceItem).filter_by(id=wid, user_id=user_id).first()
            if wi:
                wi.workspace_id = target_workspace_id
        session.commit()
    return jsonify({'status': True, 'moved': len(item_ids)})


@api_bp.route('/workspace-items/bulk-delete', methods=['POST'])
def bulk_delete_items():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    item_ids = data.get('item_ids', [])
    if not item_ids:
        return jsonify({'status': False, 'error': 'item_ids required'}), 400
    now = int(__import__('time').time())
    with db.SessionLocal() as session:
        for wid in item_ids:
            wi = session.query(db.WorkspaceItem).filter_by(id=wid, user_id=user_id).first()
            if wi:
                wi.deleted_at = now
        session.commit()
    return jsonify({'status': True, 'deleted': len(item_ids)})


@api_bp.route('/workspace-items/bulk-tag', methods=['POST'])
def bulk_tag_items():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    item_ids = data.get('item_ids', [])
    tag_id = data.get('tag_id')
    if not item_ids or not tag_id:
        return jsonify({'status': False, 'error': 'item_ids and tag_id required'}), 400
    count = 0
    for wid in item_ids:
        result = db.add_tag_to_workspace_item(wid, tag_id)
        if result:
            count += 1
    return jsonify({'status': True, 'tagged': count})


@api_bp.route('/workspace-items/bulk-export', methods=['POST'])
def bulk_export():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    item_ids = data.get('item_ids', [])
    fmt = data.get('format', 'apa')
    if not item_ids:
        return jsonify({'status': False, 'error': 'item_ids required'}), 400
    items_list = db.get_workspace_items(user_id)
    selected = [it for it in items_list if it['id'] in item_ids]
    citations = []
    for it in selected:
        title = it.get('title', '')
        source_name = it.get('source_name', '')
        url = it.get('source_url', '')
        authors = it.get('authors', '')
        year = it.get('year', '')
        if fmt == 'apa':
            cit = f"{authors} ({year}). {title}. {source_name}. {url}"
        elif fmt == 'harvard':
            cit = f"{authors} ({year}) '{title}', {source_name}. Available at: {url}"
        elif fmt == 'mla':
            cit = f"{authors}. \"{title}.\" {source_name}, {year}, {url}."
        elif fmt == 'chicago':
            cit = f"{authors}. \"{title}.\" {source_name} ({year}). {url}."
        else:
            cit = f"{title} - {url}"
        citations.append(cit)
    return jsonify({'status': True, 'citations': citations, 'format': fmt})


# ========== Cross-Workspace Search ==========

@api_bp.route('/search-all-workspaces')
def search_all_workspaces():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    q = request.args.get('q', '').strip().lower()
    if not q or len(q) < 2:
        return jsonify({'status': False, 'error': 'Query too short'}), 400
    workspaces = db.get_user_workspaces(user_id)
    results = {}
    for ws in workspaces:
        if q in ws['name'].lower():
            if ws['id'] not in results:
                results[ws['id']] = {'workspace': ws, 'items': [], 'notes': []}
        items = db.get_workspace_items(user_id, ws['id'])
        for item in items:
            title = (item.get('title') or '').lower()
            snippet = (item.get('summary') or '').lower()
            if q in title or q in snippet:
                if ws['id'] not in results:
                    results[ws['id']] = {'workspace': ws, 'items': [], 'notes': []}
                results[ws['id']]['items'].append(item)
        notes = db.get_workspace_notes(ws['id'], user_id)
        for note in notes:
            title = (note.get('title') or '').lower()
            content = (note.get('content') or '').lower()
            if q in title or q in content:
                if ws['id'] not in results:
                    results[ws['id']] = {'workspace': ws, 'items': [], 'notes': []}
                results[ws['id']]['notes'].append(note)
    return jsonify({'status': True, 'results': list(results.values())})


# ========== AI Streaming & Tools ==========

@api_bp.route('/chat/stream', methods=['POST'])
def chat_stream():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.get_json(silent=True) or {}
    messages = data.get('messages', [])
    atn = data.get('atn')
    workspace_id = data.get('workspace_id')
    persona = data.get('persona', 'formal')

    if not messages:
        return jsonify({'status': False, 'error': 'No messages provided'}), 400

    latest_user_content = next((
        message.get('content')
        for message in reversed(messages)
        if isinstance(message, dict)
        and message.get('role') == 'user'
        and isinstance(message.get('content'), str)
        and message.get('content').strip()
    ), None)
    if latest_user_content is None:
        return jsonify({'status': False, 'error': 'No user message provided'}), 400

    if workspace_id is not None:
        try:
            workspace_id = int(workspace_id)
        except (TypeError, ValueError):
            return jsonify({'status': False, 'error': 'Invalid workspace ID'}), 400
        workspace = db.get_workspace(user_id, workspace_id)
        if not workspace:
            return jsonify({'status': False, 'error': 'Workspace not found'}), 404
        persona = workspace.get('persona', persona)

    def generate():
        final_result = None
        for chunk in answer.chat_with_sources_streaming(
            user_content=latest_user_content,
            atn=atn,
            workspace_id=workspace_id,
            user_id=user_id,
            persona=persona,
        ):
            if isinstance(chunk, str) and chunk.startswith("__CITATIONS__:"):
                final_result = chunk
            else:
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

        if final_result:
            citations_json = final_result[len("__CITATIONS__:"):]
            yield f"data: {json.dumps({'type': 'citations', 'citations': citations_json})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@api_bp.route('/usage/dashboard')
def usage_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    days = request.args.get('days', 30, type=int)
    aggregates = db.get_user_usage(user_id, days=days)
    total_cost = db.get_total_user_cost(user_id)

    # Compute model distribution
    model_dist = {}
    for row in aggregates:
        model = row.get("endpoint", "unknown")
        model_dist[model] = model_dist.get(model, 0) + row.get("calls", 0)

    return jsonify({
        'status': True,
        'aggregates': aggregates,
        'total_cost': total_cost,
        'model_distribution': [{"model": k, "calls": v} for k, v in model_dist.items()],
    })


@api_bp.route('/check-similarity', methods=['POST'])
def check_similarity():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    draft = data.get('draft', '')
    workspace_id = data.get('workspace_id')

    if not draft:
        return jsonify({'status': False, 'error': 'Draft text required'}), 400
    if not workspace_id:
        return jsonify({'status': False, 'error': 'workspace_id required'}), 400

    items = db.get_workspace_items(user_id, workspace_id) or []
    source_texts = []
    for item in items:
        title = item.get("title", "Untitled")
        url = item.get("source_url", "")
        text = (item.get("abstract") or item.get("summary") or "")[:5000]
        if text:
            source_texts.append((title, url, text))
        # Also check uploaded file extracted text
        if item.get("file_id"):
            files_list = db.get_workspace_uploaded_files(workspace_id, user_id)
            for f in files_list:
                if f.get("extracted_text"):
                    source_texts.append((f.get("filename", "File"), f.get("stored_path", ""), f["extracted_text"][:5000]))

    from src.similarity import check_similarity as run_check
    results = run_check(draft, source_texts)
    return jsonify({'status': True, 'results': results})


@api_bp.route('/flashcards', methods=['POST'])
def api_flashcards():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    data = request.json
    workspace_id = data.get('workspace_id')
    if not workspace_id:
        return jsonify({'status': False, 'error': 'workspace_id required'}), 400

    flashcards = answer.generate_flashcards(workspace_id, user_id)
    return jsonify({'status': True, 'flashcards': flashcards})


@api_bp.route('/workspace/<int:workspace_id>/flashcards/export')
def export_flashcards(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    fmt = request.args.get('format', 'csv')
    flashcards = answer.generate_flashcards(workspace_id, user_id)

    if fmt == 'anki':
        try:
            import genanki
            deck = genanki.Deck(workspace_id, f"Workspace {workspace_id} Flashcards")
            for i, card in enumerate(flashcards):
                model = genanki.Model(
                    workspace_id * 1000 + i,
                    f"Card Model {i}",
                    fields=[
                        {"name": "Front"},
                        {"name": "Back"},
                    ],
                    templates=[{
                        "qfmt": "{{Front}}",
                        "afmt": "{{FrontSide}}\n\n<hr id=answer>\n\n{{Back}}",
                    }],
                )
                note = genanki.Note(model=model, fields=[card.get("front", ""), card.get("back", "")])
                deck.add_note(note)
            package = genanki.Package(deck)
            import io
            buf = io.BytesIO()
            package.write_to_file(buf)
            buf.seek(0)
            return send_file(
                buf,
                mimetype='application/apkg',
                as_attachment=True,
                download_name='flashcards.apkg',
            )
        except ImportError:
            return jsonify({'status': False, 'error': 'genanki library not installed'}), 500
    else:
        import io
        import csv
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['question', 'answer'])
        for card in flashcards:
            writer.writerow([card.get("front", ""), card.get("back", "")])
        return Response(
            buf.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=flashcards.csv'},
        )


@api_bp.route('/workspace/<int:workspace_id>/diversity')
def source_diversity(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    from urllib.parse import urlparse
    items = db.get_workspace_items(user_id, workspace_id) or []
    domain_counts = {}
    total = len(items)

    for item in items:
        url = item.get("source_url", "")
        if url:
            try:
                domain = urlparse(url).netloc
                if not domain:
                    domain = "unknown"
            except Exception:
                domain = "unknown"
        else:
            domain = "unknown"
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    distribution = [
        {"domain": domain, "count": count, "percentage": round(count / total, 3) if total > 0 else 0}
        for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    # Diversity score: 1 - sum of squared proportions (Herfindahl index)
    if total > 1:
        sum_squares = sum((count / total) ** 2 for count in domain_counts.values())
        diversity_score = 1 - sum_squares
    else:
        diversity_score = 0.0

    return jsonify({
        'status': True,
        'distribution': distribution,
        'diversity_score': round(diversity_score, 3),
        'total_sources': total,
    })


# ========== Notes with Version History ==========

@api_bp.route('/notes', methods=['GET', 'POST'])
def api_notes():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    if request.method == 'POST':
        data = request.json
        title = data.get('title', '').strip()
        content = data.get('content', '')
        if not title:
            return jsonify({'status': False, 'error': 'Title required'}), 400
        note = db.create_note(user_id, title, content)
        logging.info(f"User {user_id} created note {note['id']}")
        return jsonify({'status': True, 'note': note})
    else:
        notes = db.get_notes(user_id)
        return jsonify({'status': True, 'notes': notes})


@api_bp.route('/notes/<int:note_id>', methods=['GET', 'PUT', 'DELETE'])
def api_note(note_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    if request.method == 'GET':
        note = db.get_note(note_id, user_id)
        if not note:
            return jsonify({'status': False, 'error': 'Not found'}), 404
        return jsonify({'status': True, 'note': note})
    elif request.method == 'PUT':
        data = request.json
        title = data.get('title')
        content = data.get('content')
        note = db.update_note(note_id, user_id, title=title, content=content)
        if not note:
            return jsonify({'status': False, 'error': 'Not found'}), 404
        # Save version snapshot
        db.save_note_version(note_id, note['content'], note['title'])
        logging.info(f"User {user_id} updated note {note_id}")
        return jsonify({'status': True, 'note': note})
    elif request.method == 'DELETE':
        result = db.delete_note(note_id, user_id)
        if not result:
            return jsonify({'status': False, 'error': 'Not found'}), 404
        logging.info(f"User {user_id} deleted note {note_id}")
        return jsonify({'status': True})


# ========== Comment Endpoints ==========


@api_bp.route('/workspace-items/<int:item_id>/comments', methods=['GET'])
def list_comments(item_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    comments = db.get_comments(item_id)
    return jsonify({'status': True, 'comments': comments})


@api_bp.route('/workspace-items/<int:item_id>/comments', methods=['POST'])
def add_comment(item_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    body = (data.get('body') or '').strip()
    if not body:
        return jsonify({'status': False, 'error': 'Comment body required'}), 400
    comment = db.add_comment(item_id, user_id, body)
    logging.info(f"User {user_id} commented on workspace item {item_id}")
    return jsonify({'status': True, 'comment': comment})


@api_bp.route('/comments/<int:comment_id>/resolve', methods=['POST'])
def resolve_comment(comment_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    if db.resolve_comment(comment_id, user_id):
        logging.info(f"User {user_id} resolved comment {comment_id}")
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Comment not found'}), 404


@api_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    if db.delete_comment(comment_id, user_id):
        logging.info(f"User {user_id} deleted comment {comment_id}")
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Comment not found'}), 404


# ========== Activity Feed Endpoint ==========


@api_bp.route('/workspace/<int:workspace_id>/activity', methods=['GET'])
@require_workspace_role('viewer')
def workspace_activity(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    limit = request.args.get('limit', 50, type=int)
    activity = db.get_workspace_activity(workspace_id, limit=limit)
    return jsonify({'status': True, 'activity': activity})


# ========== Search Alerts ==========

@api_bp.route('/search-alerts', methods=['POST'])
def create_search_alert():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    query = data.get('query', '').strip()
    sources = data.get('sources', [])
    frequency = data.get('frequency', 'daily')
    if not query:
        return jsonify({'status': False, 'error': 'Query required'}), 400
    alert = db.create_search_alert(user_id, query, json.dumps(sources), frequency)
    logging.info(f"User {user_id} created search alert for '{query}'")
    return jsonify({'status': True, 'alert': alert})


@api_bp.route('/search-alerts', methods=['GET'])
def list_search_alerts():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    alerts = db.get_user_search_alerts(user_id)
    return jsonify({'status': True, 'alerts': alerts})


@api_bp.route('/search-alerts/<int:alert_id>', methods=['DELETE'])
def delete_search_alert_route(alert_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    if db.delete_search_alert(alert_id, user_id):
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Not found'}), 404


# ========== Notifications ==========

@api_bp.route('/notifications', methods=['GET'])
def list_notifications():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    unread_only = request.args.get('unread_only', '').lower() == 'true'
    notifs = db.get_user_notifications(user_id, unread_only=unread_only)
    return jsonify({'status': True, 'notifications': notifs})


@api_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_read_route(notification_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    if db.mark_notification_read(notification_id, user_id):
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Not found'}), 404


# ========== Semantic Search ==========

@api_bp.route('/search/semantic', methods=['POST'])
def semantic_search():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    query = data.get('query', '').strip()
    workspace_id = data.get('workspace_id')
    if not query:
        return jsonify({'status': False, 'error': 'Query required'}), 400
    query_embedding = embeddings.compute_simple_embedding(query)
    results = db.semantic_search_files(user_id, query_embedding, top_k=5)
    return jsonify({'status': True, 'results': results})


# ========== Citation Graph (Semantic Scholar) ==========

@api_bp.route('/citation-graph')
def citation_graph():
    paper_id = request.args.get('paper_id', '')
    ref_type = request.args.get('type', 'citations')
    if not paper_id:
        return jsonify({'status': False, 'error': 'paper_id required'}), 400
    if ref_type == 'citations':
        results = semantic_scholar.get_citations(paper_id)
    elif ref_type == 'references':
        results = semantic_scholar.get_references(paper_id)
    else:
        return jsonify({'status': False, 'error': 'Invalid type'}), 400
    return jsonify({'status': True, 'results': results})


# ========== File Pages Search ==========

@api_bp.route('/files/<int:file_id>/pages')
def search_file_pages(file_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'status': False, 'error': 'Query required'}), 400
    results = db.search_file_pages(file_id, q)
    return jsonify({'status': True, 'results': results})


# ========== Related by Keywords ==========

@api_bp.route('/related-by-keywords')
def related_by_keywords():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    title = request.args.get('title', '').strip()
    source = request.args.get('source', '').strip()
    if not title or not source:
        return jsonify({'status': False, 'error': 'title and source required'}), 400

    keywords = title[:100]
    results = []
    if source == 'wikipedia':
        results = search.wikipedia(keywords, 5, user_id=user_id)
    elif source == 'gbooks' or source == 'google books':
        results = search.gbooks(keywords, 5, {}, user_id=user_id)
    elif source == 'semantic_scholar':
        results = search.semantic_scholar(keywords, 5, user_id=user_id)
    elif source == 'openstax':
        results = search.oer_search(keywords, 5, user_id=user_id)
    else:
        results = search.browse_serpapi_search(keywords, 5, source, {}, user_id=user_id)
    return jsonify({'status': True, 'results': results})


# ========== English Subject Routes ==========

@api_bp.route('/english/prescribed-texts')
def english_prescribed_texts():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'status': True, 'texts': list(english.PRESCRIBED_TEXTS.keys())})
    result = english.find_prescribed_text(q)
    return jsonify({'status': True, 'texts': [result] if result else []})


@api_bp.route('/english/related-texts')
def english_related_texts():
    title = request.args.get('title', '').strip()
    themes_str = request.args.get('themes', '')
    themes = [t.strip() for t in themes_str.split(',') if t.strip()] if themes_str else None
    if not title:
        return jsonify({'status': False, 'error': 'title required'}), 400
    results = english.find_related_texts(title, themes)
    return jsonify({'status': True, 'results': results})


@api_bp.route('/english/literary-criticism')
def english_literary_criticism():
    text = request.args.get('text', '').strip()
    author = request.args.get('author', '').strip()
    if not text:
        return jsonify({'status': False, 'error': 'text required'}), 400
    results = english.get_literary_criticism(text, author)
    return jsonify({'status': True, 'results': results})


# ========== Mathematics Subject Routes ==========

@api_bp.route('/math/solve', methods=['POST'])
def math_solve():
    data = request.json
    equation = data.get('equation', '').strip()
    variable = data.get('variable', 'x')
    if not equation:
        return jsonify({'status': False, 'error': 'equation required'}), 400
    result = mathematics.solve_equation(equation, variable)
    return jsonify({'status': True, 'result': result})


@api_bp.route('/math/differentiate', methods=['POST'])
def math_differentiate():
    data = request.json
    expression = data.get('expression', '').strip()
    variable = data.get('variable', 'x')
    if not expression:
        return jsonify({'status': False, 'error': 'expression required'}), 400
    result = mathematics.differentiate(expression, variable)
    return jsonify({'status': True, 'result': result})


@api_bp.route('/math/integrate', methods=['POST'])
def math_integrate():
    data = request.json
    expression = data.get('expression', '').strip()
    variable = data.get('variable', 'x')
    if not expression:
        return jsonify({'status': False, 'error': 'expression required'}), 400
    result = mathematics.integrate(expression, variable)
    return jsonify({'status': True, 'result': result})


@api_bp.route('/math/graph')
def math_graph():
    expr = request.args.get('expr', '').strip()
    graph_type = request.args.get('type', 'function')
    if not expr:
        return jsonify({'status': False, 'error': 'expr required'}), 400
    url = mathematics.get_desmos_embed_url(expr, graph_type)
    return jsonify({'status': True, 'url': url})


# ========== Legal Studies (AustLII) Routes ==========

@api_bp.route('/legal/search-cases')
def legal_search_cases():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'status': False, 'error': 'q required'}), 400
    results = austlii.search_cases(q)
    return jsonify({'status': True, 'results': results})


@api_bp.route('/legal/search-legislation')
def legal_search_legislation():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'status': False, 'error': 'q required'}), 400
    results = austlii.search_cases(q)
    return jsonify({'status': True, 'results': results})


@api_bp.route('/legal/citation')
def legal_citation():
    case_name = request.args.get('case', '').strip()
    if not case_name:
        return jsonify({'status': False, 'error': 'case required'}), 400
    return jsonify({
        'status': True,
        'citation': f'*{case_name}* [2024] HCA 1',
        'components': {
            'name': case_name,
            'year': '2024',
            'court': 'HCA',
            'number': '1',
        }
    })


# ========== Geography/Economics Data Routes ==========

@api_bp.route('/abs/search')
def abs_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'status': True, 'datasets': list(abs_data.DATASETS.keys())})
    results = abs_data.search_datasets(q)
    return jsonify({'status': True, 'datasets': results})


@api_bp.route('/abs/data/<code>')
def abs_data_route(code):
    data = abs_data.get_dataset_data(code.upper())
    if not data:
        return jsonify({'status': False, 'error': 'Dataset not found'}), 404
    return jsonify({'status': True, 'data': data})


@api_bp.route('/rba/cash-rate')
def rba_cash_rate():
    data = rba_data.get_cash_rate()
    return jsonify({'status': True, 'data': data})


# ========== Creative Arts Routes ==========

@api_bp.route('/art/search')
def art_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'status': False, 'error': 'q required'}), 400
    nga_results = gallery_search.search_nga(q)
    ngv_results = gallery_search.search_ngv(q)
    return jsonify({'status': True, 'results': nga_results + ngv_results})


# ========== Aboriginal Studies (AIATSIS) Routes ==========

@api_bp.route('/aiatsis/search')
def aiatsis_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'status': False, 'error': 'q required'}), 400
    results = aiatsis.search_catalogue(q)
    return jsonify({'status': True, 'results': results})


# ========== TAS Subject Routes ==========

@api_bp.route('/tas/food')
def tas_food():
    q = request.args.get('q', '').strip()
    api_key = request.args.get('api_key', '')
    if not q:
        return jsonify({'status': False, 'error': 'q required'}), 400
    results = tas.search_food(q, api_key)
    return jsonify({'status': True, 'results': results})


@api_bp.route('/tas/materials')
def tas_materials():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'status': False, 'error': 'q required'}), 400
    results = tas.search_materials(q)
    return jsonify({'status': True, 'results': results})


# ========== Dashboard Route ==========

@api_bp.route('/dashboard')
def api_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = dashboard.get_dashboard_data(user_id)
    return jsonify({'status': True, 'dashboard': data})


# ========== NESA Curriculum Routes ==========

@api_bp.route('/nesa/courses', methods=['GET'])
def nesa_courses():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    kla = request.args.get('kla')
    courses = db.get_nesa_courses(kla=kla)
    return jsonify({'status': True, 'courses': courses})


@api_bp.route('/nesa/courses/<int:course_id>/outcomes', methods=['GET'])
def nesa_course_outcomes(course_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    outcomes = db.get_course_outcomes(course_id)
    return jsonify({'status': True, 'outcomes': outcomes})


@api_bp.route('/nesa/suggest-outcomes', methods=['POST'])
def nesa_suggest_outcomes():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    summary = data.get('summary', '')
    course_id = data.get('course_id')
    if not summary or not course_id:
        return jsonify({'status': False, 'error': 'summary and course_id required'}), 400
    suggestions = db.suggest_outcomes(summary, course_id)
    return jsonify({'status': True, 'suggestions': suggestions})


@api_bp.route('/workspace-items/<int:item_id>/outcomes', methods=['POST'])
def tag_item_outcome(item_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    outcome_id = data.get('outcome_id')
    if not outcome_id:
        return jsonify({'status': False, 'error': 'outcome_id required'}), 400
    result = db.tag_item_with_outcome(item_id, outcome_id)
    if not result:
        return jsonify({'status': False, 'error': 'Already tagged or not found'}), 400
    return jsonify({'status': True, 'tag': result})


@api_bp.route('/workspace/<int:workspace_id>/outcomes-report', methods=['GET'])
def workspace_outcomes_report(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    outcomes = db.get_workspace_outcomes(workspace_id, user_id)
    return jsonify({'status': True, 'outcomes': outcomes})


# ========== Explain Rubric ==========

@api_bp.route('/explain-rubric', methods=['POST'])
def explain_rubric():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    criteria_text = data.get('criteria_text', '')
    target_band = data.get('target_band', 'Band 6')
    draft_text = data.get('draft_text', '')
    if not criteria_text:
        return jsonify({'status': False, 'error': 'criteria_text required'}), 400
    result = answer.explain_rubric(criteria_text, target_band, draft_text)
    return jsonify({'status': True, 'explanation': result.get('explanation', '')})


# ========== Class/Teacher Routes ==========

@api_bp.route('/classes/create', methods=['POST'])
def create_class():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    name = data.get('name', '').strip()
    course_id = data.get('course_id')
    if not name:
        return jsonify({'status': False, 'error': 'Name required'}), 400
    cls = db.create_class(user_id, name, course_id=course_id)
    return jsonify({'status': True, 'class': cls})


@api_bp.route('/classes/join', methods=['POST'])
def join_class():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    join_code = data.get('join_code', '').strip()
    if not join_code:
        return jsonify({'status': False, 'error': 'join_code required'}), 400
    result = db.join_class(join_code, user_id)
    if not result:
        return jsonify({'status': False, 'error': 'Invalid join code'}), 404
    return jsonify({'status': True, 'membership': result})


@api_bp.route('/classes', methods=['GET'])
def list_classes():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    teacher_classes = db.get_teacher_classes(user_id)
    student_classes = db.get_student_classes(user_id)
    return jsonify({'status': True, 'teaching': teacher_classes, 'enrolled': student_classes})


@api_bp.route('/classes/<int:class_id>/students', methods=['GET'])
def class_students(class_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    students = db.get_class_students(class_id)
    return jsonify({'status': True, 'students': students})


@api_bp.route('/classes/<int:class_id>/workspaces', methods=['GET'])
def class_workspaces(class_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    workspaces = db.get_class_workspaces(class_id, user_id)
    return jsonify({'status': True, 'workspaces': workspaces})


@api_bp.route('/classes/<int:class_id>/push-workspace', methods=['POST'])
def push_class_workspace(class_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    template_id = data.get('template_id')
    if not template_id:
        return jsonify({'status': False, 'error': 'template_id required'}), 400
    from backend.workspace_routes import WORKSPACE_TEMPLATES
    template = next((t for t in WORKSPACE_TEMPLATES if t['id'] == template_id), None)
    if not template:
        return jsonify({'status': False, 'error': 'Template not found'}), 404
    students = db.get_class_students(class_id)
    pushed = []
    for s in students:
        ws = db.create_workspace(s["id"], template["name"])
        db.set_workspace_persona(ws["id"], s["id"], "tutor")
        for section in template.get("structure", {}).get("note_sections", []):
            db.create_workspace_note(s["id"], ws["id"], section, f"<h3>{section}</h3><p>Your notes here...</p>")
        pushed.append({"student_id": s["id"], "workspace_id": ws["id"], "workspace_name": ws["name"]})
    return jsonify({'status': True, 'pushed': pushed})


@api_bp.route('/classes/<int:class_id>/analytics', methods=['GET'])
def class_analytics(class_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    analytics = db.get_class_analytics(class_id, user_id)
    if not analytics:
        return jsonify({'status': False, 'error': 'Class not found or not your class'}), 404
    return jsonify({'status': True, 'analytics': analytics})
