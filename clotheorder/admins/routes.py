from flask import jsonify, request, session, Blueprint
import bcrypt
from clotheorder import conn
from clotheorder import psycopg2

from flask_jwt_extended import jwt_required
from flask_jwt_extended import create_access_token
from flask_jwt_extended import get_jwt
from clotheorder import format_timestamp as ft

# create an instance of this Blueprint
admins = Blueprint('admins','__name__')


# management

# Create a route to authenticate your admins and return token.
@admins.route('/clotheorder/admin/login', methods=['POST'])
def login():
    _json = request.json
    # validate the received values
    if 'phonenumber' in _json.keys() and 'password' in _json.keys():
        _phonenumber = _json['phonenumber']
        _password = _json['password']
        # check admin exists
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        sql = """
        SELECT 
            userid,password,rolename,status
        FROM 
            users 
        WHERE 
            phonenumber = %s 
        AND 
            rolename = %s
        """
        sql_where = (_phonenumber,'admin')

        cursor.execute(sql, sql_where)
        row = cursor.fetchone()
        cursor.close()
        if row:
            password_hash = row['password']
            userid = row['userid']
            rolename = row['rolename']
            status = row['status']
            if status == 'inactive':
                resp = jsonify({"message":"Locked - Your account is locked! You can contact with our employee to know reason!"})
                resp.status_code = 423
                return resp
            elif bcrypt.checkpw(_password.encode('utf-8'), password_hash.encode('utf-8')):
                # create token
                additional_claims = {"rolename":rolename}
                access_token = create_access_token(identity=userid,additional_claims=additional_claims)
                session['access_token'] = access_token
                resp = jsonify(access_token=access_token)
                resp.status_code = 200
                return resp
            else:
                resp = jsonify({'message': 'Bad Request - Wrong password!'})
                resp.status_code = 400
                return resp
        else:
            resp = jsonify({'message': 'Bad Request - Your account does not exist in the system!'})
            resp.status_code = 400
            return resp
    else:
        resp = jsonify({'message': 'Bad Request - Missing input!'})
        resp.status_code = 400
        return resp


## admin updates order status to 'Delivering'
@admins.route('/clotheorder/admin/order/update/<int:orderid>',methods=['PUT'])
@jwt_required()
def orderStatusUpdate(orderid):
    info = get_jwt()
    rolename = info['rolename']
    
    if rolename == 'admin':
        # check order status is 'Preparing'or not.
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        sql_check_preparing = """
        SELECT orderid FROM orders
        WHERE orderid = %s AND status = %s
        """
        sql_where = (orderid,'Preparing')
        cursor.execute(sql_check_preparing,sql_where)
        row = cursor.fetchone()
        if row:
            sql = """
            UPDATE orders
            SET status = 'Delivering'
            WHERE orderid = %s
            """
            sql_where = (orderid,)
            cursor.execute(sql,sql_where)
            conn.commit()
            cursor.close()
            resp = jsonify({"message":"Updated order status to 'Delivering'!"})
            resp.status_code = 200
            return resp
        else:
            cursor.close()
            resp = jsonify({"message":"You're cannot change the order status to 'Delivering'!"})
            resp.status_code = 400
            return resp
    else:
        resp = jsonify({"message":"Unauthorized - You are not authorized!"})
        resp.status_code = 401
        return resp

## get customer info
@admins.route('/clotheorder/admin/customer/info',methods=['GET'])
@jwt_required()
def getCustomerInfo():
    data = get_jwt()
    rolename = data['rolename']

    if rolename == 'admin':
        sql = """
        SELECT userid,phonenumber,fullname,address,email,status FROM users
        WHERE rolename = 'user'
        ORDER BY userid
        """
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(sql)
        info = cursor.fetchall()
        customerInfo = [{'userid':i['userid'],'phonenumber':i['phonenumber'],
                         'fullname':i['fullname'],'address':i['address'],'email':i['email'],
                         'status':i['status']} for i in info]
        cursor.close()
        resp = jsonify(data=customerInfo)
        resp.status_code = 200
        return resp
    else:
        resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
        resp.status_code = 401
        return resp


## Lock and unlock customer accounts
@admins.route('/clotheorder/admin/customer/status/<int:userid>', methods = ['PUT'])
@jwt_required()
def changeCustomerStatus(userid):
    data = get_jwt()
    rolename = data['rolename']

    if rolename == 'admin':
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # if the user status is active then i will change it to inactive and ngược lại
        sql_check_status = """
        SELECT status FROM users
        WHERE userid = %s
        """
        sql_where = (userid,)
        cursor.execute(sql_check_status,sql_where)
        userStatus = cursor.fetchone()[0]

        _status = ''
        if userStatus == 'active':
            _status = 'inactive'
        elif userStatus == 'inactive':
            _status = 'active'

        # change user status
        sql_change_status = """
        UPDATE users
        SET status = %s
        WHERE userid = %s
        """
        sql_where = (_status,userid)
        cursor.execute(sql_change_status,sql_where)
        conn.commit()
        cursor.close()
        resp = jsonify({'message':'Changed customer account status!!'})
        resp.status_code = 200
        return resp

    else:
        resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
        resp.status_code = 401
        return resp


## Admin: CURD clothe (get all clothe and clothe detail already available APIs)

## Create clothes
@admins.route('/clotheorder/admin/clothe/create', methods = ['POST'])
@jwt_required()
def createclothe():
    data = get_jwt()
    rolename = data['rolename']
    
    if rolename == 'admin':
        _json = request.json
        _clothename = _json['clothename']
        _clotheimage = _json['clotheimage']
        _description = _json['description']
        _categoryid = _json['categoryid']
        _sizeArr = _json['size']
        _colorArr = _json['color']

        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # add info clothe
        sql_create_clothe = """
        INSERT INTO 
            clothes(clothename,clotheimage,description,categoryid,status)
        VALUES
            (%s,%s,%s,%s,%s)
        RETURNING
            clotheid
        """
        sql_where = (_clothename,_clotheimage,_description,_categoryid,'Available')
        
        cursor.execute(sql_create_clothe,sql_where)
        row = cursor.fetchone()
        clotheid = row[0]

        # add info size
        if _sizeArr != []:
            for i in _sizeArr:
                sql_add_size = """
                INSERT INTO sizes(namesize,price,clotheid) VALUES(%s,%s,%s)
                """
                sql_where = (i['namesize'],i['price'],clotheid)
                cursor.execute(sql_add_size,sql_where)
        else:
            resp = jsonify({'message':"Missing input - You have to add size of clothe!!"})
            resp.status_code = 400
            return resp

        # add info color(if any)
        if _colorArr != []:
            # add info color to colors table
            lst_colorid = []
            for i in _colorArr:
                sql_add_color = """
                INSERT INTO colors(namecolor,price) VALUES(%s,%s)
                RETURNING colorid
                """
                sql_where = (i['namecolor'],i['price'])
                cursor.execute(sql_add_color,sql_where)
                colorid = cursor.fetchone()
                lst_colorid.append(colorid[0])
            
            # add colorid to clothecolor table
            for i in lst_colorid:
                sql_clothecolor = """
                INSERT INTO clothecolor(clotheid,colorid) VALUES(%s,%s)
                """
                sql_where = (clotheid,i)
                cursor.execute(sql_clothecolor,sql_where)
        
        # commit it to DB
        conn.commit()
        cursor.close()
        resp = jsonify({'message':"Add clothe success!!"})
        resp.status_code = 200
        return resp
    
    else:
        resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
        resp.status_code = 401
        return resp

## Update and detete clothe
@admins.route('/clotheorder/admin/clothe/<int:clotheid>', methods = ['PUT', 'DELETE'])
@jwt_required()
def admimGetAllclothe(clotheid):
    data = get_jwt()
    rolename = data['rolename']

    if rolename == 'admin':
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if request.method == 'PUT':
            _json = request.json
            _clotheid = _json['clotheid']
            _clothename = _json['clothename']
            _clotheimage = _json['clotheimage']
            _description = _json['description']
            _categoryid = _json['categoryid']
            _sizeArr = _json['size']
            _colorArr = _json['color']
            
            # change clothe info
            sql_change_clothe = """
            UPDATE
                clothes
            SET
                clothename = %s,clotheimage = %s, description = %s, categoryid = %s
            WHERE clotheid = %s
            """
            sql_where = (_clothename,_clotheimage,_description,_categoryid,_clotheid)
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute(sql_change_clothe,sql_where)
            
            # change size of clothe
            if _sizeArr != []:
                # If the request body has sizeid means that it already exists in the system
                # otherwise it doesn't exists and we have to create it in DB
                for i in _sizeArr:
                    # there are sizeid (we just change it)
                    if 'sizeid' in i:
                        _sizeid = i['sizeid']
                        _namesize = i['namesize']
                        _price = i['price']

                        sql_change_size = """
                        UPDATE
                            sizes
                        SET
                            namesize = %s, price = %s
                        WHERE
                            sizeid = %s
                        """
                        sql_where = (_namesize,_price,_sizeid)
                        cursor.execute(sql_change_size,sql_where)
                    # there are no sizeid (we have to create it)
                    else:
                        _namesize = i['namesize']
                        _price = i['price']

                        sql_create_size = """
                        INSERT INTO
                            sizes(namesize,price,clotheid)
                        VALUES(%s,%s,%s)
                        """
                        sql_where = (_namesize,_price,_clotheid)
                        cursor.execute(sql_create_size,sql_where)
            else:
                resp = jsonify({'message':"Missing input - You have to add size of clothe!!"})
                resp.status_code = 400
                return resp
            
            # change color of clothe (if any)
            if _colorArr != []:
                # If the request body has colorid means that it already exists in the system
                # otherwise it doesn't exists and we have to create it in DB
                for i in _colorArr:
                    # there are color (we just change it)
                    if "colorid" in i:
                        _colorid = i['colorid']
                        _namecolor = i['namecolor']
                        _price = i['price']

                        sql_change_color = """
                        UPDATE
                            colors
                        SET
                            namecolor = %s, price = %s
                        WHERE
                            colorid = %s
                        """
                        sql_where = (_namecolor,_price,_colorid)
                        cursor.execute(sql_change_color,sql_where)
                    # there are no colorid (we have to create it)
                    else:
                        _namecolor = i['namecolor']
                        _price = i['price']
                        # we have create color in colors table
                        # get colorid and save it in clothecolor table
                        sql_create_color = """
                        INSERT INTO
                            colors(namecolor,price)
                        VALUES(%s,%s)
                        RETURNING colorid
                        """
                        sql_where = (_namecolor,_price)
                        cursor.execute(sql_create_color,sql_where)
                        row = cursor.fetchone()
                        colorid = row[0]
                        # save colorid to clothecolor table
                        sql_add_clothecolor = """
                        INSERT INTO
                            clothecolor(clotheid,colorid)
                        VALUES(%s,%s)
                        """
                        sql_where = (_clotheid,colorid)
                        cursor.execute(sql_add_clothecolor,sql_where)

            conn.commit()
            cursor.close()
            resp = jsonify({'message':"Update success!"})
            resp.status_code = 200
            return resp

        elif request.method == 'DELETE':
            sql_detete_clothe = """
            UPDATE clothes
            SET status = 'Unvailable'
            WHERE clotheid = %s
            """
            sql_where = (clotheid,)
            cursor.execute(sql_detete_clothe,sql_where)
            conn.commit()
            cursor.close()

            resp = jsonify({'message':"Delete Successfully!!"})
            resp.status_code = 200
            return resp
        else:
            resp = jsonify({'message':"Not Implemented!!"})
            resp.status_code = 501
            return resp
    else:
        resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
        resp.status_code = 401
        return resp


## admin view order history or current 
@admins.route('/clotheorder/admin/order/<status>', methods = ['GET'])
@jwt_required()
def adminOrderHistory(status):
    data = get_jwt()
    rolename = data['rolename']

    if rolename != 'admin':
        resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
        resp.status_code = 401
        return resp

    orderstatus = []
    if status == 'history':
        orderstatus=['Completed','Cancelled']
    elif status == 'current':
        orderstatus=['Preparing','Delivering']

    if orderstatus == []:
        resp = jsonify({"message":"Bad Request!!"})
        resp.status_code = 400
        return resp

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # admin get order 'history' or 'current'
        sql_history = """
        SELECT 
            orderid,status,address,orderdate,totalprice
        FROM orders
        WHERE 
            (status = %s OR status = %s)
        ORDER BY orderdate DESC
        """
        sql_where = (orderstatus[0],orderstatus[1])

        cursor.execute(sql_history,sql_where)
        row = cursor.fetchall()
        data = [{"orderid":i["orderid"],"status":i["status"],"address":i["address"],
                "orderdate":ft.format_timestamp(str(i["orderdate"])),"totalprice":float(i["totalprice"])} 
                for i in row]
        
        # get order detail
        lst_orderid = [i["orderid"] for i in row]
        all_order_detail = []

        for i in lst_orderid:
            sql_order_detail = """
            SELECT 
                clothename, itemquantity,namesize,namecolor
            FROM 
                itemorder as io
            INNER JOIN 
                items as i
            ON
                io.itemid = i.itemid
            INNER JOIN 
                clothes as d
            ON
                d.clotheid = i.clotheid
            INNER JOIN
                sizes as s
            ON 
                s.sizeid = i.sizeid
            LEFT JOIN
                itemcolor as it
            ON
                it.itemid = i.itemid
            LEFT JOIN 
                colors as t
            ON
                t.colorid = it.colorid
            WHERE orderid = %s
            """
            sql_where = (i,)
            cursor.execute(sql_order_detail,sql_where)
            orderdetail = cursor.fetchall()
            all_order_detail.append(orderdetail)

        # format all_order_detail
        all_order_detail_format = []
        for i in range(len(all_order_detail)):
            result = ", ".join([f"{sublist[0]} (x{sublist[1]})" for sublist in all_order_detail[i]]) + ", size " + ", ".join(set([sublist[2] for sublist in all_order_detail[i]]))
            color = [sublist[3] for sublist in all_order_detail[i] if sublist[3] is not None]
            if color:
                result += ", color: " + ", ".join([sublist[3] for sublist in all_order_detail[i] if sublist[3] is not None])
            all_order_detail_format.append(result)
        # add order detail
        for i in range(len(data)):
            data[i].update({"orderdetail":all_order_detail_format[i]})

        cursor.close()
        resp = jsonify(data=data)
        resp.status_code = 200
        return resp

    except:
        resp = jsonify({"message":"Internal Server Error!!"})
        resp.status_code = 500
        return resp


## admin cancelled order
@admins.route('/clotheorder/admin/order/cancel/<int:orderid>', methods = ['PUT'])
@jwt_required()
def adminCancelledOrder(orderid):
    data = get_jwt()
    rolename = data['rolename']

    if rolename != 'admin':
        resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
        resp.status_code = 401
        return resp
    
    # check orderid already exists and it have a 'Preparing' status 
    # then system allows for cancel order 
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    sql_check_constraint = """
    SELECT orderid FROM orders
    WHERE
        orderid = %s
        AND
        status = %s
    """

    sql_where = (orderid,'Preparing')
    cursor.execute(sql_check_constraint,sql_where)
    row = cursor.fetchone()

    if row:
        # update order status to 'Cancelled'
        sql_cancel = """
        UPDATE orders
        SET status = %s
        WHERE orderid = %s
        """
        sql_where = ('Cancelled',orderid)
        cursor.execute(sql_cancel,sql_where)
        conn.commit()
        cursor.close()
        resp = jsonify({"message":"Order status updated to 'Cancelled'!"})
        resp.status_code = 200
        return resp

    else:
        cursor.close()
        resp = jsonify({"message":"Order cannot cancel"})
        resp.status_code = 400
        return resp

## revenue statistics by day or month or year
@admins.route('/clotheorder/admin/revenue', methods=['GET'])
@jwt_required()
def getRevenue():
    data = get_jwt()
    rolename = data['rolename']

    if rolename == 'admin':
        date = request.args.get('date')
        flag = request.args.get('flag')

        revenue = 0
        revenue_detail = []
        row = [] # contain raw data when i execute sql

        # format date 'dd-mm-yy' to 'yy-mm-dd'
        date_format = date[6:10] + '-' + date[3:5] + '-' + date[0:2]
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        sql_revenue = """
        SELECT 
            orderid, totalprice, orderdate
        FROM
            orders
        WHERE 
            CAST(orderdate as TEXT) 
                LIKE 
            CONCAT(%s,%s) 
                AND 
            status = 'Completed'
        ORDER BY orderdate ASC;
        """

        if flag == 'today':
            # get total revenue
            sql_where = (date_format,'%')
            cursor.execute(sql_revenue,sql_where)
            row = cursor.fetchall()
                
        elif flag == 'month':
            sql_where = (date_format[0:7],'%')
            cursor.execute(sql_revenue,sql_where)
            row = cursor.fetchall()

        elif flag == 'year':
            sql_where = (date_format[0:4],'%')
            cursor.execute(sql_revenue,sql_where)
            row = cursor.fetchall()
        
        else:
            cursor.close()
            resp = jsonify({"message":"Invalid parameter passed!!"})
            resp.status_code = 400
            return resp
        
        # total revenue and revenue detail
        if row != None:
            for i in row:
                revenue += int(i['totalprice'])
            revenue_detail = [{'orderid':i['orderid'],'orderdate':ft.format_timestamp(str(i['orderdate'])),
                                'totalprice':i['totalprice']} for i in row]

        cursor.close()
        resp = jsonify(data = {'revenue':revenue,'revenueDetail':revenue_detail})
        resp.status_code = 200
        return resp
    else:
        resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
        resp.status_code = 401
        return resp
