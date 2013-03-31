# --------------------------------------------------
# Copyright The IETF Trust 2011, All Rights Reserved
# --------------------------------------------------

# Python libs
import os
import time
import datetime
import re
try:
    import debug
except ImportError:
    pass

# Local libs
from xml2rfc import VERSION
from xml2rfc.writers.paginated_txt import PaginatedTextRfcWriter
from xml2rfc.writers.raw_txt import RawTextRfcWriter
from compiler.pyassem import RAW

nroff_linestart_meta = ["'", ".", ]

def nroff_escape_linestart(line):
    if line.startswith("'"):
        return "\\" + line
    if line.startswith("."):
        return "\\&" + line

class NroffRfcWriter(PaginatedTextRfcWriter):
    """ Writes to an nroff formatted file

        The page width is controlled by the *width* parameter.
    """

    comment_header = '.\\" automatically generated by xml2rfc v%s on %s'

    settings_header = [
        '.pl 10.0i',      # Page length
        '.po 0',          # Page offset
        '.ll 7.2i',       # Line length
        '.lt 7.2i',       # Title length
        '.nr LL 7.2i',    # Printer line length
        '.nr LT 7.2i',    # Printer title length
        '.hy 0',          # Disable hyphenation
        '.ad l',          # Left margin adjustment only
    ]

    def __init__(self, xmlrfc, width=72, quiet=False, verbose=False, date=datetime.date.today()):
        PaginatedTextRfcWriter.__init__(self, xmlrfc, width=width, \
                                        quiet=quiet, verbose=verbose, date=date)
        self.curr_indent = 0    # Used like a state machine to control
                                # whether or not we print a .in command
        self.wrapper.width = self.width-3
        self.wrapper.post_break_replacements = {
            '&#160;' : r'\\0',  # nbsp
            '&#8209;': r'\-',  # nbhy
            '&#8288;': r'',     # wj
        }


    def _indent(self, amount):
        # Writes an indent command if it differs from the last
        if amount != self.curr_indent:
            self.write_nroff('.in ' + str(amount))
            self.curr_indent = amount

    # Override
    def _vspace(self, num=0):
        """ nroff uses a .sp command in addition to a literal blank line """
        self.write_nroff('.sp %s' % num)

    def write_nroff(self, string):
        # Used by nroff to write a line with nroff commands.  No escaping
        self.buf.append(string)

    def write_line(self, string):
        # Used by nroff to write a line with no nroff commands
        if string[0] in nroff_linestart_meta:
            string = nroff_escape_linestart(string)
        self.buf.append(string)

    # Override
    def write_text(self, string, indent=0, sub_indent=0, bullet='',
                    align='left', leading_blankline=False, buf=None,
                    strip=True, edit=False, wrap_urls=False,
                    fix_sentence_endings=True, source_line=None):
        #-------------------------------------------------------------
        # RawTextRfcWriter override
        #
        # We should be able to handle mostly all of the nroff commands by
        # intercepting the alignment and indentation arguments
        #-------------------------------------------------------------
        if not buf:
            buf = self.buf

        # Store buffer position for paging information
        begin = len(self.buf)

        if leading_blankline:
            if edit and self.pis['editing'] == 'yes':
                # Render an editing mark
                self.edit_counter += 1
                self._lb(buf=buf, text=str('<' + str(self.edit_counter) + '>'))
            else:
                self._lb(buf=buf)

        par = []
        if string:
            if strip:
                # Strip initial whitespace
                string = string.lstrip()
            if bullet and len(bullet.strip()) > 0:
                string = bullet + string
                fix_doublespace = False
            else:
                fix_doublespace = True

            par = self.wrapper.wrap(string, break_on_hyphens=False, fix_doublespace=fix_doublespace,
                                    fix_sentence_endings=fix_sentence_endings)
            # Escape as needed
            for i in range(len(par)):
                if par[i][0] in nroff_linestart_meta:
                    par[i] = nroff_escape_linestart(par[i])
            # Use bullet for indentation if sub not specified
            full_indent = sub_indent and indent + sub_indent or indent + len(bullet)

            # Handle alignment/indentation
            if align == 'center':
                self.write_nroff('.ce %s' % len(par))
            else:
                self._indent(full_indent)

        if bullet and len(bullet.strip()) > 0:
            # Bullet line: title just uses base indent
            self.write_nroff('.ti ' + str(indent))
            if not string:
                # Just write the bullet
                par.append(bullet)

        # Write to buffer
        buf.extend(par)

        # Page break information
        end = len(self.buf)
        self.break_hints[begin] = (end - begin, "txt")

        """
        elif bullet:
            # If the string is empty but a bullet was declared, just
            # print the bullet
            buf.append(initial)
        """

    def _post_write_toc(self, tmpbuf):
        # Wrap a nofill/fill block around TOC
        tmpbuf.append('.ti 0')
        tmpbuf.append('Table of Contents')
        tmpbuf.append('')
        tmpbuf.append('.in 3')
        tmpbuf.append('.nf')
        tmpbuf.extend(self.toc)
        tmpbuf.append('.fi')
        return tmpbuf

    def _expand_xref(self, xref):
        """ Returns the proper text representation of an xref element """
        target = xref.attrib.get('target', '')
        format = xref.attrib.get('format', self.defaults['xref_format'])
        item = self._getItemByAnchor(target)
        if not item or format == 'none':
            target_text = '[' + target + ']'
        elif format == 'counter':
            target_text = item.counter
        elif format == 'title':
            target_text = item.title
        else: #Default
            target_text = item.autoName
        if xref.text:
            if not target_text.startswith('['):
                target_text = '(' + target_text + ')'
            else:
                if "." in target_text or "-" in target_text:
                    target_text = "\%" + target_text
            return xref.text.rstrip() + ' ' + target_text
        else:
            if "." in target_text or "-" in target_text:
                target_text = "\%" + target_text
            return target_text

    # ---------------------------------------------------------
    # PaginatedTextRfcWriter overrides
    # ---------------------------------------------------------

    def write_title(self, text, docName=None, source_line=None):
        # Override to use .ti commands
        self._lb()
        self.write_text(text, align='center', source_line=source_line)
        if docName:
            self.write_text(docName, align='center')

    def write_raw(self, text, indent=3, align='left', blanklines=0, \
                  delimiter=None, leading_blankline=True, source_line=None):
        # Wrap in a no fill block
        self._indent(indent)
        self.write_nroff('.nf')
        PaginatedTextRfcWriter.write_raw(self, text, indent=0, align=align,
                                         blanklines=blanklines,
                                         delimiter=delimiter,
                                         leading_blankline=leading_blankline,
                                         source_line=source_line)
        self.write_nroff('.fi')

    def write_heading(self, text, bullet='', autoAnchor=None, anchor=None, \
                      level=1):
        # Override to use a .ti command
        self._lb()
        if bullet:
            bullet += '  '
        if len(bullet+text) > (self.width - 3):
            self.write_nroff('.in %s' % len(bullet))
        self.write_nroff('.ti 0')
        self.write_line(bullet + text)

    def urlkeep(self, text):
        return re.sub(r'http://', r'\%http://', text)

    def write_paragraph(self, text, align='left', autoAnchor=None):
        """ Write a generic paragraph of text.  Used for boilerplate. """
        text = self.urlkeep(text)
        self.write_text(text, indent=3, align=align, leading_blankline=True)

    def pre_indexing(self):
        # escape backslashes in the text
        for element in self.r.iter():
            if element.text:
                element.text = element.text.replace('\\', '\\\\')
            if element.tail:
                element.tail = element.tail.replace('\\', '\\\\')

    def pre_rendering(self):
        """ Inserts an nroff header into the buffer """

        # Construct the RFC header and footer
        PaginatedTextRfcWriter.pre_rendering(self)

        # Insert a timestamp+version comment
        self.write_line(self.comment_header % ('.'.join(map(str, VERSION)),
            time.strftime('%Y-%m-%dT%H:%M:%SZ', datetime.datetime.utcnow().utctimetuple())))
        self._lb()

        # Insert the standard nroff settings
        self.buf.extend(NroffRfcWriter.settings_header)

        # Insert the RFC header and footer information
        self.write_nroff('.ds LH ' + self.left_header)
        self.write_nroff('.ds CH ' + self.center_header)
        self.write_nroff('.ds RH ' + self.right_header)
        self.write_nroff('.ds LF ' + self.left_footer)
        self.write_nroff('.ds CF ' + self.center_footer)
        self.write_nroff('.ds RF FORMFEED[Page %]')

    def post_rendering(self):
        # Insert page break commands
        # Write buffer to secondary buffer, inserting breaks every 58 lines
        page_len = 0
        page_maxlen = 55
        for line_num, line in enumerate(self.buf):
            if line_num in self.break_hints:
                # If this section will exceed a page, insert a break command
                available = page_maxlen - page_len
                needed, text_type = self.break_hints[line_num]
                if line.strip() == "":
                    available -= 1
                    needed -= 1
                if (text_type == "break"
                    or (text_type == "raw" and needed > available)
                    or (self.pis['autobreaks'] == 'yes'
                        and needed > available
                        and (needed-available < 2 or available < 2) ) ):
                    self.output.append('.bp')
                    page_len = 0
            if page_len + 1 > 55:
                self.output.append('.bp')
                page_len = 0
            self.output.append(line)
            page_len += 1

    def write_to_file(self, file):
        """ Writes the buffer to the specified file """
        for line in self.output:
            file.write(line.rstrip(" \t"))
            file.write("\n")
            