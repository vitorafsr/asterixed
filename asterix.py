'''
EUROCONTROL ASTERIX encoder/decoder

A library that encodes and decodes in the standard format specified in the
document EUROCONTROL-SPEC-0149.
Edition Number: 2.2
Edition Date: 17/10/2014

Category specifications Xml files in the "config/" directory were taken from
https://github.com/CroatiaControlLtd/asterix/tree/master/install/config
These files were public under GPLv3 license.
'''

__copyright__ = '''\
The MIT License (MIT)

Copyright (c) 2014 Vitor Augusto Ferreira Santa Rita

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

#TODO: evaluate if better using lxml for performance
from xml.dom import minidom
import struct
import traceback

verbose = 1

#TODO: check files against "config/asterix.dtd" structure
filenames = \
    {1:'config/asterix_cat001_1_1.xml',
    2:'config/asterix_cat002_1_0.xml',
    8:'config/asterix_cat008_1_0.xml',
    10:'config/asterix_cat010_1_1.xml',
    19:'config/asterix_cat019_1_2.xml',
    20:'config/asterix_cat020_1_7.xml',
    #21:'config/asterix_cat021_0_26.xml',
    21:'config/asterix_cat021_1_8.xml',
    23:'config/asterix_cat023_1_2.xml',
    30:'config/asterix_cat030_6_2.xml',
    31:'config/asterix_cat031_6_2.xml',
    #32:'config/asterix_cat032_6_2.xml',
    32:'config/asterix_cat032_7_0.xml',
    48:'config/asterix_cat048_1_14.xml',
    #62:'config/asterix_cat062_0_17.xml',
    #62:'config/asterix_cat062_1_9.xml',
    62:'config/asterix_cat062_1_16.xml',
    #62:'config/asterix_cat062_1_7.xml',
    63:'config/asterix_cat063_1_3.xml',
    65:'config/asterix_cat065_1_3.xml',
    #65:'config/asterix_cat065_1_2.xml',
    242:'config/asterix_cat242_1_0.xml',
    #252:'config/asterix_cat252_6_2.xml',
    252:'config/asterix_cat252_7_0.xml'}#,
    #252:'config/asterix_cat252_6_1.xml'}


def load_asterix_category_format(cat):
    global filenames
    try:
        return minidom.parse(filenames[cat])
    except:
        traceback.print_exc()

    return None


def encode(asterix):
    assert type(asterix) is dict

    data_blocks = 0

    for k,v in asterix.iteritems():
        ctf = load_asterix_category_format(k)
        if ctf is None:
            continue

        if verbose >= 1:
            print 'encoding cat',k

        for cat_tree in ctf.getElementsByTagName('Category'):
            if k != int(cat_tree.getAttribute('id')):
                continue

            ll_db, db = encode_category(k, v, cat_tree)

            #TODO: use maximum datablock size
            data_blocks <<= ll_db*8
            data_blocks += db
            break

    return data_blocks


def encode_category(cat, did, tree):
    if did == {}:
        return 0, 0

    mdi = {}
    for c in tree.getElementsByTagName('DataItem'):
        di = c.getAttribute('id')
        if di.isdigit():
            di = int(di)
        rule = c.getAttribute('rule')
        if did.has_key(di):
            l, v = encode_dataitem(did[di],c)
            mdi[di] = l, v
        else:
            if rule == 'mandatory' and verbose >= 1:
                print 'absent mandatory dataitem',di

    datarecord = 0L
    n_octets_datarecord = 0
    sorted_mdi_keys = sorted(mdi.keys())
    for di in sorted_mdi_keys:
        l, v = mdi[di]
        datarecord <<= l*8
        datarecord += v
        n_octets_datarecord += l

    fspec_bits = []
    uap_tree = tree.getElementsByTagName('UAP')[0]
    for cn in uap_tree.childNodes:
        if cn.nodeName != 'UAPItem':
            continue
        uapi_value = cn.firstChild.nodeValue
        if uapi_value.isdigit():
            uapi_value = int(uapi_value)
        if uapi_value in sorted_mdi_keys:
            fspec_bits.append(int(cn.getAttribute('bit')))

    if fspec_bits == []:
        print 'no dataitems identified'
        return 0, 0

    # FSPEC for data record
    max_bit = max(fspec_bits)
    n_octets_fspec = max_bit/8 + 1

    # Fn
    fspec = 0
    for i in fspec_bits:
        fspec += (1 << (n_octets_fspec*8 - 1 - i))

    # FX
    for i in range(n_octets_fspec-1):
        fspec += (1 << ((n_octets_fspec-1-i)*8))

    datarecord += (fspec << (n_octets_datarecord*8))
    n_octets_datarecord += n_octets_fspec

    # data record header
    datarecord += (cat << ((n_octets_datarecord)*8 + 16))
    datarecord += ((1+2+n_octets_datarecord) << ((n_octets_datarecord)*8))

    return 1+2+n_octets_datarecord, datarecord


def encode_dataitem(dfd, tree):
    assert type(dfd) is dict or type(dfd) is list
    for c in tree.getElementsByTagName('DataItemFormat'):
        for d in c.childNodes:
            if d.nodeName == 'Fixed':
                return encode_fixed(dfd, d)
            else:
                if d.nodeName == 'Variable':
                    return encode_variable(dfd, d)
                else:
                    if d.nodeName == 'Repetitive':
                        return encode_repetitive(dfd, d)
                    else:
                        if d.nodeName == 'Compound':
                            return encode_compound(dfd, d)


def encode_fixed(bd, tree):
    length = int(tree.getAttribute('length'))
    value = 0
    has_encoded = False
    for cn in tree.childNodes:
        if cn.nodeName != 'Bits':
            continue

        key = cn.getElementsByTagName('BitsShortName')[0].firstChild.nodeValue
        if bd.has_key(key) and key != 'FX':
            has_encoded = True
            assert (cn.getAttribute('bit') == '' and (cn.getAttribute('from')!='' and cn.getAttribute('to')!='')) or (cn.getAttribute('bit') != '' and (cn.getAttribute('from')=='' and cn.getAttribute('to')==''))
            bit_ = cn.getAttribute('bit')
            if bit_ != '':
                bit_ = int(bit_)
                shift_left = bit_-1
                mask = 0x1
            else:
                from_ = int(cn.getAttribute('from'))
                to_ = int(cn.getAttribute('to'))
                if from_ < to_: # swap values
                    x = to_
                    to_ = from_
                    from_ = x
                shift_left = to_-1
                mask = (1 << (from_ - to_ + 1 + 1)) - 1

            v = bd[key]

            #TODO: consider 'encode' attr
            value += ((v & mask) << shift_left)
        else:
            if key != 'FX' and verbose >= 1:
                print 'field',key,'absent in input'

    if has_encoded == False:
        return 0, 0

    return length, value


def encode_variable(db, tree): # Extended
    variable = None
    length = 0
    for cn in tree.childNodes:
        if cn.nodeName == 'Fixed':
            l, v = encode_fixed(db, cn)
            assert l <= 1
            if l > 0:
                if v % 2 == 1: # remove FX
                    v -= 1

                length += 1
                if variable is None:
                    variable = v
                else:
                    variable += 1 # add FX
                    variable <<= 8
                    variable += v
            else:
                break

    return length, variable


def encode_repetitive(db, tree):
    found = False
    cn = None
    for cn in tree.childNodes:
        if cn.nodeName == 'Fixed':
            found = True
            break # found

    if found == False:
        if verbose >= 1:
            print 'Repetitive node not found'
        return 0, 0

    assert type(db) is list
    length = 0
    value = 0
    rep = len(db)
    for i in range(rep):
        l, v = encode_fixed(db[i], cn)
        assert l > 0

        length += l
        value <<= (8*l)
        value += v

    value += (rep << (8*length)) # add REP header
    return length+1, value


def encode_compound(db, tree):
    length = 0
    data = 0
    sf = 0
    subfields = []
    for cn in tree.childNodes:
        l = 0
        if cn.nodeName == 'Variable':
            l, v = encode_variable(db, cn)
        else:
            if cn.nodeName == 'Fixed':
                l, v = encode_fixed(db, cn)
            else:
                if cn.nodeName == 'Repetitive':
                    l, v = encode_repetitive(db, cn)
                else:
                    if cn.nodeName == 'Variable':
                        l, v = encode_variable(db, cn)
                    else:
                        if cn.nodeName == 'Compound':
                            l, v = encode_compound(db, cn)

        if l > 0:
            subfields.append(sf)
            length += l
            data <<= (8*l)
            data += v

        sf += 1

    n_octets = max(subfields)/7 + 1
    primary_subfield = 0
    for i in sorted(subfields): # subfields
        primary_subfield += (1 << (8*(i/7) + (8 - (i%7))))
    for i in range(n_octets-1): # FX
        primary_subfield += (1 << 8*(i+1))

    data += (primary_subfield << (8*length))

    return length + n_octets, data


def decode_file(filename):
    try:
        fp = open(filename, 'r')
        x = decode(fp)
        fp.close()
        return x
    except:
        print traceback.print_exc()


def decode(stream):
    l, r = decode_record(stream)
    if l > 0:
        return r

    return {}


def decode_record(stream):
    cat_s = stream.read(1)
    if len(cat_s) == 0:
        return 0, {}
    (cat,) = struct.unpack('B', cat_s)
    if verbose >= 1:
        print 'decoding cat',cat

    acf = load_asterix_category_format(cat)
    if acf is None:
        return 0, {}

    found = False
    tree = None
    for tree in acf.getElementsByTagName('Category'):
        id_ = int(tree.getAttribute('id'))
        if id_ == cat:
            found = True
            break

    if found == False:
        if verbose >= 1:
            print 'category not found in configs files'
        return 0, {}

    assert int(tree.getAttribute('id')) == cat
    (length,) = struct.unpack('>H', stream.read(2))
    fspec_bits = []
    on = 0 # octet number
    while True:
        (fspec_octet,) =  struct.unpack('B', stream.read(1))
        for i in range(1, 8):
            if (fspec_octet >> i) & 1 == 1:
                fspec_bits.append(on*8+7-i)
        if fspec_octet & 1 == 0:
            break
        on += 1

    # identify dataitems
    dis = []
    uap_tree = tree.getElementsByTagName('UAP')[0]
    for cn in uap_tree.childNodes:
        if cn.nodeName != 'UAPItem':
            continue
        uapi_bit = int(cn.getAttribute('bit'))
        if uapi_bit in fspec_bits:
            di = cn.firstChild.nodeValue
            if di.isdigit():
                di = int(di)
            dis.append(di)

    # decode dataitems
    results = {}
    length = 0
    for di in sorted(dis):
        if verbose >= 1:
            print 'decoding dataitem',di
        l, r = decode_datafield(stream, di, tree)
        results.update({di:r})
        length += l

    return length, {cat:results}


def decode_datafield(stream, di, tree):
    for cn in tree.getElementsByTagName('DataItem'):
        if cn.nodeName != 'DataItem':
            continue
        id_ = cn.getAttribute('id')
        if id_.isdigit():
            id_ = int(id_)

        if id_ != di:
            continue

        for cnn in cn.getElementsByTagName('DataItemFormat'):
            for cnnn in cnn.childNodes:
                if cnnn.nodeName == 'Fixed':
                    return decode_fixed(stream, cnnn)
                else:
                    if cnnn.nodeName == 'Repetitive':
                        return decode_repetitive(stream, cnnn)
                    else:
                        if cnnn.nodeName == 'Variable':
                            return decode_variable(stream, cnnn)
                        else:
                            if cnnn.nodeName == 'Compound':
                                return decode_compound(stream, cnnn)

    return 0, {}


def decode_fixed(stream, tree):
    length = int(tree.getAttribute('length'))
    octets = struct.unpack(str(length)+'B', stream.read(length))

    data = 0
    for v in octets:
        data <<= 8
        data += v

    # iterate over fields
    di = {}
    for cn in tree.getElementsByTagName('Bits'):
        if cn.nodeName != 'Bits':
            continue

        bit_name = cn.getElementsByTagName('BitsShortName')[0].firstChild.nodeValue

        assert (cn.getAttribute('bit') == '' and (cn.getAttribute('from')!='' and cn.getAttribute('to')!='')) or (cn.getAttribute('bit') != '' and (cn.getAttribute('from')=='' and cn.getAttribute('to')==''))
        bit = cn.getAttribute('bit')
        if bit != '':
            bit = int(bit)

            #TODO: consider 'encode' attr
            di[bit_name] = ((data >> (bit-1)) & 1)
        else:
            from_ = int(cn.getAttribute('from'))
            to_ = int(cn.getAttribute('to'))
            if from_ < to_: # swap values
                x = to_
                to_ = from_
                from_ = x
            mask = (1 << (from_ - to_ + 1)) - 1

            #TODO: consider 'encode' attr
            di[bit_name] = ((data >> (to_ - 1)) & mask)

        #TODO: treat others attributes

    return length, di


def decode_variable(stream, tree):
    length = 0
    results = {}
    for cn in tree.childNodes:
        if cn.nodeName == 'Fixed':
            l, r = decode_fixed(stream, cn)
            length += l
            results.update(r)
            assert r.has_key('FX')
            if r['FX'] == 0:
                return length, results

    return length, results


def decode_repetitive(stream, tree):
    (rep,) = struct.unpack('B', stream.read(1))

    length = 0
    results = []
    for i in range(rep):
        for cn in tree.childNodes:
            if cn.nodeName == 'Fixed':
                l, r = decode_fixed(stream, cn)
                length += l
                results.append(r)

    return length, results


def decode_compound(stream, tree):
    #identifying subfields numbers
    subfields = []
    oc = 0
    while True:
        (octet,) = struct.unpack('B', stream.read(1))
        for i in range(1,8):
            if (octet >> i) & 1 == 1:
                subfields.append(oc*8 + 7 - i)
        if (octet & 1) == 0: # FX zero
            break
        oc += 1

    if verbose >= 1:
        print 'subfields',subfields

    sf = 0
    results = {}
    length = 0
    for cn in tree.childNodes:
        if cn.nodeName == '#text':
            continue

        if sf in subfields:
            l, r = {}, 0
            if cn.nodeName == 'Fixed':
                l, r = decode_fixed(stream, cn)
            else:
                if cn.nodeName == 'Variable':
                    l, r = decode_variable(stream, cn)
                else:
                    if cn.nodeName == 'Repetitive':
                        l, r = decode_repetitive(stream, cn)
                    else:
                        if cn.nodeName == 'Explicit':
                            l, r = decode_explicit(stream, cn)

            assert l > 0
            results.update(r)
            length += l

        sf += 1

    return length, results


def decode_explicit(stream, tree):
    #TODO: implement
    return 0, {}


def tofile(x, filename):
    bytes = []
    while x > 0:
        bytes.append(x&0xff)
        x >>=8

    try:
        fp = open(filename, 'wb')
        for b in reversed(bytes):
            fp.write(chr(b))

        fp.close()
    except Exception, e:
        print str(e)
