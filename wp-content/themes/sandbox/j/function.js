(function($){


  //cookies handling
  $.cookie = {
    get: function(c_name){
      var i,x,y,c=document.cookie.split(";");
      for (i=0;i<c.length;i++){
        x=c[i].substr(0,c[i].indexOf("="));
        y=c[i].substr(c[i].indexOf("=")+1);
        x=x.replace(/^\s+|\s+$/g,"");
        if (x==c_name){
          return unescape(y);
        }
      }
    },
    set: function(c_name,value,exdays){
      var exdate=new Date();
      exdate.setDate(exdate.getDate() + exdays);
      var c_value=escape(value) + ((exdays==null) ? "" : "; expires="+exdate.toUTCString());
      document.cookie=c_name + "=" + c_value;
    }
  };


})(window.jQuery);
