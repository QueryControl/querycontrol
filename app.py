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
import re
import json
import urllib
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'this_should_be_configured')
socrata_app_token = os.environ.get("SOCRATA_APP_TOKEN") # allows access to private datasets shared with the user app token tied to
filters_dataset_domain = os.environ.get("FILTERS_DATASET_DOMAIN", "communities.socrata.com")
filters_datasetid = os.environ.get("FILTERS_DATASETID", "b9dt-4hh2")

import sys
import logging

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

def validate_url(domain, datasetid, url):
    if not "$select" in url:
        return {"error": "$select required"}
    if "*" in url:
        return {"error": "* not allowed"}
    if "$query" in url:
        return {"error": "$query not allowed"}
    print 'https://%s/resource/%s.json?domain=%s&datasetid=%s' % (filters_dataset_domain, filters_datasetid, domain, datasetid)
    dataset_filter = requests.get('https://%s/resource/%s.json?domain=%s&datasetid=%s' % (filters_dataset_domain, filters_datasetid, domain, datasetid)).json()
    print 'dataset_filter', dataset_filter
    if dataset_filter:
        dataset_filter = json.loads(dataset_filter[0]['filter'])
        print 'actual filter', dataset_filter
        # get field names
        columns = requests.get('https://%s/api/views/%s.json' % (domain, datasetid)).json()['columns']
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
        return Response(json.dumps(requests.get(url).json()),  mimetype='application/json')
    else:
        return Response(json.dumps(url),  mimetype='application/json')

@app.route('/forsocrata/<domain>/<datasetid>.json/fieldnames/')
@cross_origin()
def for_socrata_get_fieldnames(domain, datasetid):
    columns = requests.get('https://%s/api/views/%s.json' % (domain, datasetid)).json()['columns']
    fieldnames = [item['fieldName'] for item in columns]
    return Response(json.dumps(fieldnames),  mimetype='application/json')

@app.errorhandler(404)
def page_not_found(error):
    """Custom 404 page."""
    return render_template('404.html'), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=True, port=port)
