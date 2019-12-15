#!/usr/bin/env python3

# Convert an Inkscape SVG file into a set of PDF slides for presentation
# or printing.
#
# Requires inkscape and pdftk to be installed and in the PATH.
#
# This is a fork of mkpdfs.py (https://gist.github.com/stevenbell/909c79c9396f932942476e658b38d80c)
# from Steven Bell, which in turn was inspired by mkpdfs.rb (https://gist.github.com/emk/961877)
#
# By default, each layer in the SVG file produces one slide. If there are sublayers
# each of them will make a slide, with the parent layer being added (this only goes
# one level deep, subsublayers are not supported).
# Layers are ordered from bottom to top (i.e., the bottom layer is the first slide).

# A layer whose name begins with '_' will be used as a "base" layer for all
#   slides that follow.
# A layer whose name begins with '.' will always be hidden.  This is useful for
#   guides, templates, or just hiding things that aren't finished.
# A layer whose name begins with '+' will be added to the previous layer, as if it were
# a sublayer. The script actually begins by flattening the layer structure, taking out
# sublayers and pre-pending "+" to the name. If you desire, you can start with a flat
# layer structure and use "+" directly rather than using sublayers.
#
# There are a set of special tags that will get filled in when placed in a text
# field as ${tag}.  Currently the only tag is ${slide}, which inserts the slide
# number.  This only works for normal text fields, not text boxes.

from lxml import etree
import os
from sys import argv
import filecmp

# Configuration
if len(argv) < 2:
    print("Incorrect number of arguments")
    print("Usage: presentink.py SVGFILE\n")
    exit()

srcfile = argv[1]
tmpdir = '.tmpdir'
tmpsvg = tmpdir+os.path.sep+'temp.svg'
coalesce_animations = False # Whether to flatten animations for printouts

if not os.path.isdir(tmpdir):
    os.system("mkdir "+tmpdir)

# Load the file and get the namespaces
doc = etree.fromstringlist(open(srcfile)).getroottree()
ns = doc.getroot().nsmap
layers = doc.findall('/svg:g[@inkscape:groupmode="layer"]', namespaces=ns)

#remove unnecesary information, otherwise this leads to unnecesary inkscape stuff causing recreation of pdfs
namedviews = doc.findall("{"+ns["sodipodi"]+'}namedview')
if len(namedviews) == 0:
    print("Did not find information to strip in inkscape file, continuing")
for namedview in namedviews:
    namedview.getparent().remove(namedview)

# Find all the text strings that we're going to have to replace
texts = doc.findall('//tspan', namespaces=ns)
subst_elements = [] # Text elements where we have to substitute something
subst_strings = [] # The corresponding strings of text

for t in texts:
    if t.text is not None and t.text.find('${slide}') is not -1:
        subst_elements.append(t)
        subst_strings.append(t.text)

# Zeroth pass:
# If some layers have sublayers, flatten the document by making the sublayers
# main layers with "+" pre-pended to the name.
# This only goes one layer deep
for l in layers:
    sublayers = l.findall('g[@inkscape:groupmode="layer"]', namespaces=ns)[::-1]
    for sl in sublayers:
        # add a '+' to the label so we know this is a sublayer
        # add nothing if the slide already has a specific symbol
        l.addnext(sl)
        label = sl.attrib['{'+ns['inkscape']+'}label']
        if (len(label)>0 and label[0] not in ['+','_','!','-','.']):
            sl.attrib['{'+ns['inkscape']+'}label'] = "+"+label
layers = doc.findall('/svg:g[@inkscape:groupmode="layer"]', namespaces=ns)

# First pass:
# Make all of the layers invisible
# and find the last layer which should be visible
last_visible_layer = None
for l in layers:
    l.attrib['style'] = 'display:none'
    label = l.attrib['{'+ns['inkscape']+'}label']
    if label[0] is not '.' and label[0] is not '_':
        last_visible_layer = l

# Second pass:
# Build up the layers and create files
slide_num = 0 # Number that we put into slides
page_count = 0 # Used to name the PDF files we export, name is (slide_num)_(page_count),
               # and page count is reset for each new normal layer.

base_layers = [] # Layers which are always shown once added
visible_layers = [] # Layers visible in current slide
additional_layers = [] # Layers marked with + (or that were sublayers)

pdf_path_list = "" # string with names of all pdfs to join

for i,l in enumerate(layers):

    label = l.attrib['{'+ns['inkscape']+'}label']
    if label[0] is '.':
        # Hidden, just skip this layer
        continue
    elif label[0] is '-':
        # clear additional layers and go to the next one
        # if slide title is just "-", clear all additional slides
        if len(label) == 1:
            additional_layers = []
        else:
            #text after "-" should be an integer, and will remove
            # as many slides as indicated
            try:
                number_to_remove = int(label[1:])
                if len(additional_layers) < number_to_remove:
                    additional_layers = []
                else:
                    additional_layers = additional_layers[:len(additional_layers)-number_to_remove]
            except ValueError:
                #Handle the exception
                print("ERROR: wrong name for layer titled "+label)
                print("layers starting with '-' should have an integer, or nothing following")
                sys.exit(0)
        continue
    elif label[0] is '!':
        # clear base layers and go to the next one. Change will appear
        # at the next normal slide
        # if slide title is just "!", clear all base slides
        if len(label) == 1:
            base_layers = []
        else:
            #text after "!" should be an integer, and will remove
            # as many slides as indicated
            try:
                number_to_remove = int(label[1:])
                if len(base_layers) < number_to_remove:
                    base_layers = []
                else:
                    base_layers = base_layers[:len(base_layers)-number_to_remove]
            except ValueError:
                #Handle the exception
                print("ERROR: wrong name for layer titled "+label)
                print("layers starting with '!' should have an integer, or nothing following")
                sys.exit(0)
        continue
    elif label[0] is '_':
        # Base layer, add it to the list but don't make a slide for it
        base_layers.append(l)
        continue
    elif label[0] is '+':
        # Additive layer, just append it to the current list
        additional_layers.append(l);
    else:
        # Normal case, reset all the layers and add this one
        additional_layers = []
        visible_layers = base_layers + [l];
        slide_num += 1
        page_count = 0

    if coalesce_animations and l is not last_visible_layer:
        next_label = layers[i+1].attrib['{http://www.inkscape.org/namespaces/inkscape}label']
        if next_label[0] is '+' or next_label[0] is '.':
            # Then don't render just yet
            print("skipping!")
            continue

    for vl in visible_layers + additional_layers:
        vl.attrib['style'] = 'display:inline'

    # Do the string substitutions
    for s in range(len(subst_elements)):
        subst_elements[s].text = subst_strings[s].replace('${slide}', str(slide_num))

    # Save the updated SVG file
    doc.write(tmpsvg)
    # open the updated SVG, trim it of non visible items and save back
    tmpdoc = etree.fromstringlist(open(tmpsvg)).getroottree()
    tmplayers = tmpdoc.findall('/svg:g[@inkscape:groupmode="layer"]', namespaces=ns)
    for tmp_l in tmplayers:
        if tmp_l.attrib['style'] == 'display:none':
            tmp_l.getparent().remove(tmp_l)
    tmpdoc.write(tmpsvg)

    # Call Inkscape to render it
    pdf_name = tmpdir + os.path.sep + "slide-{:03d}_{:03d}.pdf".format(slide_num, page_count)
    page_count += 1

    pdf_path_list += pdf_name + " "
    
    # Check if it's neccesary to render this file again
    final_svg_name = tmpdir+os.path.sep+"slide-{:03d}_{:03d}.svg".format(slide_num, page_count-1)
    if os.path.isfile(pdf_name):
        if os.path.isfile(final_svg_name) and \
                filecmp.cmp(final_svg_name, tmpsvg):
            # already created this svg, just move on
            print("Skipping "+pdf_name)
            # Restore things back to the way they were for the next run
            for vl in visible_layers + additional_layers:
                vl.attrib['style'] = 'display:none'
            continue

    # this is a new svg, move it to its final location
    os.system("mv "+tmpsvg+" "+final_svg_name)

    print("Exporting {id} as {name}".format(id=l.attrib['id'], name=pdf_name))
    # calling inkscape with "export-ignore-filters" prevents rasterization of embedded pdfs
    os.system("inkscape --export-ignore-filters --export-pdf={path} --export-area-page {svgfile}".format(path=pdf_name, svgfile=final_svg_name))

    # Restore things back to the way they were for the next run
    for vl in visible_layers + additional_layers:
        vl.attrib['style'] = 'display:none'

# Merge everything using pdftk
out_path = srcfile[:-4] + '.pdf'
if os.system("pdftk "+pdf_path_list+" cat output {}".format(out_path)):
    print("Failed to combine pdfs!  Check that pdftk is installed")
else:
    print("Output written to {}".format(out_path))

