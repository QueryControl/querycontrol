"""
Flask Documentation:     http://flask.pocoo.org/docs/
Jinja2 Documentation:    http://jinja.pocoo.org/2/documentation/
Werkzeug Documentation:  http://werkzeug.pocoo.org/documentation/

This file creates your application.
"""

import os
from flask import Flask, Response, render_template, request, redirect, url_for
import flask
app = Flask(__name__)
from flask_cors import *
import requests
from requests.auth import HTTPBasicAuth
import re
import json
import urllib
from sodapy import Socrata
from datetime import datetime
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'this_should_be_configured')
socrata_app_token = os.environ.get("socrata_app_token") # allows access to private datasets shared with the user app token tied to
# oauth for Socrata is unusable for us because tokens expire in a short period of time and it doesn't allow refreshing tokens
socrata_username = os.environ.get("socrata_username")
socrata_password = os.environ.get("socrata_password")
socrata_access_log_domain = os.environ.get("socrata_access_log_domain")
socrata_access_log_datasetid = os.environ.get("socrata_access_log_datasetid")
filters_dataset_domain = os.environ.get("FILTERS_DATASET_DOMAIN", "communities.socrata.com")
filters_datasetid = os.environ.get("FILTERS_DATASETID", "b9dt-4hh2")

import sys
import logging

@app.before_request
def log_request():
    print 'log_request', request.url
    print (socrata_app_token and socrata_username and socrata_password and socrata_access_log_domain and socrata_access_log_datasetid)
    if socrata_app_token and socrata_username and socrata_password and socrata_access_log_domain and socrata_access_log_datasetid:
        client = Socrata(socrata_access_log_domain, socrata_app_token, username=socrata_username, password=socrata_password)
        
        # fix this, see http://esd.io/blog/flask-apps-heroku-real-ip-spoofing.html
        if not request.headers.getlist("X-Forwarded-For"):
            ip = request.remote_addr
        else:
            ip = request.headers.getlist("X-Forwarded-For")[0]
        # for some reason a space and a * is causing an upsert error so am replacing space with %20
        url = str(request.url).replace(" ", "%20")
        # See Socrata's time format https://support.socrata.com/hc/en-us/articles/202949918-Importing-Data-Types-and-You-
        dtnow = datetime.utcnow().isoformat()
        dtnow = dtnow[:dtnow.index('.')]+'Z' 
        data = [{'datetime': dtnow, 'ip_address': str(ip), 'url': url}]
        print data
        print 'upsert', client.upsert(socrata_access_log_datasetid, data)
        
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)
###
# Routing for your application.
###

@app.route('/')
def home():
    """Render website's home page."""
    return render_template('home.html')


@app.route('/about/')
def about():
    """Render the website's about page."""
    return render_template('about.html')

import requests
import re

@app.route('/filter_editor/')
def filter_editor():
    return render_template('filter_editor.html')

def validate_url(domain, datasetid, url):
    if not "$select" in url:
        return {"error": "$select required"}
    if re.search('[=,:]\s*\*', url):
        return {"error": "selecting * or :* not allowed"}
    if "$query" in url:
        return {"error": "$query not allowed"}
    print 'https://%s/resource/%s.json?domain=%s&datasetid=%s' % (filters_dataset_domain, filters_datasetid, domain, datasetid)
    dataset_filter = requests.get('https://%s/resource/%s.json?domain=%s&datasetid=%s' % (filters_dataset_domain, filters_datasetid, domain, datasetid)).json()
    print 'dataset_filter', dataset_filter
    if requests.get('https://%s/resource/%s.json' % (domain, datasetid)).json() == {u'message': u'You must be logged in to access this resource', u'error': True} and not dataset_filter:
        return {"error": "dataset requested is a private dataset without a filter so no public access is allowed"}
    if dataset_filter:
        dataset_filter = json.loads(dataset_filter[0]['filter'])
        print 'actual filter', dataset_filter
        # get field names
        columns = requests.get('https://%s/api/views/%s.json' % (domain, datasetid), auth=HTTPBasicAuth(socrata_username, socrata_password)).json()['columns']
        fieldnames = [item['fieldName'] for item in columns]
        query_part = url[url.index('?')+1:]
        query_parts = dict([item.split('=')[:2] for item in query_part.split('&')])
        as_fields_from_filter = []
        for fieldtype in re.findall('\$([a-z]+)=', url):
            if fieldtype in ['order', 'limit']:
                continue
            if not fieldtype+'_fields' in dataset_filter:
                return {"error": "$%s not in filter" % (fieldtype)}
            for fieldname in dataset_filter[fieldtype+'_fields']:
                if ' as ' in fieldname:
                    parts = fieldname.split(' as ')
                    as_fields_from_filter.append(parts)
            not_allowed_fieldnames = list(set(fieldnames) - set(dataset_filter[fieldtype+'_fields']))
            print fieldtype, not_allowed_fieldnames
            for fieldname in not_allowed_fieldnames:
                if fieldname in query_parts['$'+fieldtype]:
                    return {"error": "%s not allowed in $%s" % (fieldname, fieldtype)}
        if as_fields_from_filter:
            parts = url.split('&')
            for i, part in enumerate(parts):
                for field in as_fields_from_filter:
                    if '$select' in part:
                        parts[i] = parts[i].replace('='+field[1], '='+field[0]+' as '+field[1])
                        parts[i] = parts[i].replace(','+field[1], ','+field[0]+' as '+field[1])
                    else:
                        parts[i] = parts[i].replace('='+field[1], '='+field[0])
                        parts[i] = parts[i].replace(','+field[1], ','+field[0])
            url = '&'.join(parts)
        print url
        return url
    return

def parse_url(url):
    if ":total_count" in url:
        if not "$group" in url:
            url = url.replace(":total_count", "count(*)")
        else:
            count_url = url[:url.find('.json')+5] + '?$select=count(*) as count'
            if socrata_username and socrata_password:
                total_count = requests.get(count_url, auth=HTTPBasicAuth(socrata_username, socrata_password)).json()[0]['count']
            else:
                total_count = requests.get(count_url).json()[0]['count']
            url = url.replace(":total_count", total_count)
    m = re.search(',:group_count WHERE \((?P<where_expression>.*?)\)/:group_count as (?P<as>[a-zA-Z]+)[,&]', urllib.unquote(url))
    if m:
        print m.group('where_expression')
        modified_url = urllib.unquote(url).replace(m.group()[:-1], ',count(*) as [REPLACEWITHAS]').replace('%2F', '/')
        if '$order' in modified_url:
            
            modified_url = modified_url.replace(re.search('&\$order=.*', modified_url).group(), '')
        if '$where' in modified_url:
            print modified_url
            where_section = re.search("(?P<replace>\$where=.*)[\&]*", modified_url).group('replace')
            print where_section
            numerator_url = modified_url.replace(where_section, where_section + ' AND ' + m.group('where_expression'))
        else:
            numerator_url = modified_url + '&$where=' + m.group('where_expression')
        numerator_url = numerator_url.replace('[REPLACEWITHAS]', 'numerator')
        print numerator_url
        denominator_url = modified_url.replace('[REPLACEWITHAS]', 'denominator')
        print denominator_url
        print "NU", numerator_url
        if socrata_username and socrata_password:
            numerators = requests.get(numerator_url, auth=HTTPBasicAuth(socrata_username, socrata_password)).json()
            denominators = requests.get(denominator_url, auth=HTTPBasicAuth(socrata_username, socrata_password)).json()
        else:
            numerators = requests.get(numerator_url).json()
            denominators = requests.get(denominator_url).json()
        percentages = []
        for row in numerators:
            print 'row', row
            modified_row = row.copy()
            del modified_row['numerator']
            for mrow in denominators:
                match = True
                for col in modified_row:
                    if modified_row.get(col) != mrow.get(col):
                        match = False
                        break
                if match:
                    matching_denominator_row = mrow
            modified_row['percentage'] = float(row['numerator'])/float(matching_denominator_row['denominator'])
            percentages.append(modified_row)
        return sorted(percentages, key=lambda x: x.get('percentage'), reverse=True)
    if ":group_count" in url:
        url = url.replace(":group_count", "count(*)")
    return url

@app.route('/forsocrata/<domain>/<datasetid>.json/')
@cross_origin()
def for_socrata(domain, datasetid):
    """
    Do not use count(*). Use :total_count for the count(*) of the total dataset and
    :group_count for count(*) of a groupping. 
    """
    if not "?" in request.url:
        return json.dumps({"error": "$select required"})
    url = 'https://%s/resource/%s.json%s' % (domain, datasetid, request.url[request.url.index('?'):])
    url = str(url)
    is_error = validate_url(domain, datasetid, url)
    if isinstance(is_error, dict):
        return Response(json.dumps(is_error), mimetype='application/json')
    elif is_error:
        url = str(is_error)
    url = str(url)
    url = parse_url(url)
    print url, isinstance(url, str), type(url)
    # this code is messy because during parsing if any custom stuff is done like the WHERE in a $select
    # then rows are returned instead of a url
    if isinstance(url, str) or isinstance(url, unicode):
        print 'is string'
        return Response(json.dumps(requests.get(url, auth=HTTPBasicAuth(socrata_username, socrata_password)).json()),  mimetype='application/json')
    else:
        return Response(json.dumps(url),  mimetype='application/json')

@app.route('/forsocrata/sql/')
@cross_origin()
def for_socrata_sql():
    print 'for socrata sql being ran'
    from pandasql import sqldf
    import inspect
    print 'sqldf arguments', inspect.getargspec(sqldf)
    import string, random
    dbid = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
    pysqldf = lambda q: sqldf(q, globals(), db_uri='sqlite:///%s.db' % (dbid))
    #return 'trying to fix memory issue'
    import pandas as pd
    import io
    import requests
    sql = request.args.get('q')
    # we expect FROM [[ socrata_domain ]]:[[ dataset_id ]]
    # SELECT * FROM data.seattle.gov:y7pv-r3kh JOIN data.seattle.gov:pu5n-trf4 ON data.seattle.gov:y7pv-r3kh.general_offense_number = data.seattle.gov:pu5n-trf4.general_offense_number
    froms = list(set(re.findall('FROM [a-zA-Z0-9\.]+:[a-zA-Z0-9\-]+', sql)))
    variables = []
    for f in froms:
        fparts = f.split(' ')[1].split(':')
        url = "http://%s/resource/%s.csv?$order=:created_at DESC&$limit=2000" % (fparts[0], fparts[1])
        s = requests.get(url).content
        variable = '_'.join(fparts).replace('.', '_').replace('-', '_')
        #print variable
        # changing globals() to locals() didn't work
        variables.append(variable)
        globals()[variable] = pd.read_csv(io.StringIO(s.decode('utf-8')))
        #print globals()[variable]
        sql = sql.replace(f, 'FROM ' + variable)
        sql = sql.replace(f.split(' ')[1], variable)
    froms = list(set(re.findall('JOIN [a-zA-Z0-9\.]+:[a-zA-Z0-9\-]+', sql)))
    for f in froms:
        fparts = f.split(' ')[1].split(':')
        url = "http://%s/resource/%s.csv" % (fparts[0], fparts[1])
        s = requests.get(url).content
        variable = '_'.join(fparts).replace('.', '_').replace('-', '_')
        #print variable
        # changing globals() to locals() didn't work
        globals()[variable] = pd.read_csv(io.StringIO(s.decode('utf-8')))
        #print globals()[variable]
        sql = sql.replace(f, 'JOIN ' + variable)
        sql = sql.replace(f.split(' ')[1], variable)
    
    df = pysqldf(sql)
    Cols = list(df.columns)
    for i,item in enumerate(df.columns):
        
        if item in df.columns[:i]: Cols[i] = "toDROP"
    df.columns = Cols
    try:
        df = df.drop("toDROP",1)
    except:
        pass 
    for variable in variables:
        del globals()[variable]
    return Response(df.to_json(orient='records'), mimetype='application/json')
    
@app.route('/forsocrata/<domain>/<datasetid>/fieldnames/')
@cross_origin()
def for_socrata_get_fieldnames(domain, datasetid):
    if socrata_username and socrata_password:
        columns = requests.get('https://%s/api/views/%s.json' % (domain, datasetid), auth=HTTPBasicAuth(socrata_username, socrata_password)).json()['columns']
    else:
        columns = requests.get('https://%s/api/views/%s.json' % (domain, datasetid)).json()['columns']
    fieldnames = [item['fieldName'] for item in columns]
    return Response(json.dumps(fieldnames),  mimetype='application/json')

@app.route('/forsocrata/owned_datasets/')
@cross_origin()
def for_socrata_owned_datasets():
    userid = requests.get("https://%s/api/users/current.json" % (socrata_access_log_domain), auth=HTTPBasicAuth(socrata_username, socrata_password)).json()['id']
    datasets = requests.get('https://%s/api/search/views.json?accessType=WEBSITE&limit=10&page=1&sortBy=newest&for_user=%s&nofederate=true&publication_stage%%5B%%5D=published&publication_stage%%5B%%5D=unpublished&id=%s&row_count=3' % (socrata_access_log_domain, userid, userid), auth=HTTPBasicAuth(socrata_username, socrata_password)).json()['results']
    datasets = [dataset['view'] for dataset in datasets]
    return Response(json.dumps(datasets), mimetype='application/json')

@app.errorhandler(404)
def page_not_found(error):
    """Custom 404 page."""
    return render_template('404.html'), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=True, port=port)
