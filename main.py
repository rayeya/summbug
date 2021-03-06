#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import webapp2, jinja2, os, itertools
import bugretriever
from lexrank import bugreport_tokenizer, lexrank
from lexrank.extractive_summary import Sentence
import logging, traceback

jinja_environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

def handle_404(request, response, exception):
    logging.exception(exception)
    response.write('Oops! I could swear this page was here!')
    response.set_status(404)

def handle_500(request, response, exception):
    logging.exception(exception)
    response.write('A server error occurred!')
    response.set_status(500)

### user can select section of bug and ask to expand on that
### this should show snippets of the top n most related portions of the 
### bug just beside it. use can click on snippet, which will scroll
### the page to the comment and set the selected sentence  as relevant in the summary.
### this should allow the user to 'build' the summary as he goes along.

### generating summary:
# - retrieving bug;
# - finding sentences;
# - summarizing;
# - also retrieve the similarity matrix from lexrank algorithm,
#   since we will use this to locate relevant sentences;

def get_bug(project, bug_id):
    return bugretriever.retrieve(project, bug_id)

def split_sentences(bug):
    return [Sentence((i,j), s, bug.id)
            for i,c in enumerate(bug.comments)
            for j,s in enumerate(
                    split_sent_to_html(bugreport_tokenizer.split_sentences(c.text)))]

def split_sent_to_html(sents):
    return list(sents)

def thread_to_sentences(thread):
    sentences = [Sentence((i,j), s, thread.id) for i,m in enumerate(thread.messages) for j,s in enumerate(m.sentences)]
    return sentences

class HomeHandler(webapp2.RequestHandler):
    def get(self):
        template = jinja_environment.get_template('index.html')
        self.response.out.write(template.render({}))

class MainHandler(webapp2.RequestHandler):
    def get(self, project, bug_id):
        if project.lower() not in ['debian', 'mozilla']:
            self.response.out.write('Project %s is not yet supported.' % project)
            return
        
        if 'load' in self.request.GET:
            try:
                bug = get_bug(project, int(bug_id))
            except Exception:
                logging.warn(traceback.format_exc())
                self.response.out.write('''
                <div class="container">
                  <div class="loading-status alert" style="width:200px;">Bug not found</div>
                </div>''')
                return
            
            sents = split_sentences(bug)

            summarizer = lexrank.LexrankSummarizer()
            summary,_ = summarizer.summarize(sents, target_wc_perc=0.25, title=bug.title)
            in_summary = set(s.id for s in summary)

            for i,comment_sents in itertools.groupby(sents, key=lambda s: s.id[0]):
                bug.comments[i].text = [{'text': s.text, 'included': s.id in in_summary} for s in comment_sents]

            template_values = {
                'bug': bug,
                'non_empty_comments': set(c.number for c in bug.comments
                                          if any(sent['included'] for sent in c.text))
            }

            template = jinja_environment.get_template('bug_report.html')
            self.response.out.write(template.render(template_values))
        else:
            template_values = {
                'title': '%s %s' % (project, bug_id),
                'project': project
            }
            template = jinja_environment.get_template('loading_bug.html')
            self.response.out.write(template.render(template_values))

app = webapp2.WSGIApplication([('/([a-zA-Z\-_]*)/([0-9]*)', MainHandler),
                               ('/(?:index.html)?', HomeHandler)],
                              debug=True)
app.error_handlers[404] = handle_404
app.error_handlers[500] = handle_500
    
