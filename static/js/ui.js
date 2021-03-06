
function imgurl(id, link) {
	node = document.getElementById(id);
	node.src = link.href;
	$('html,body').animate({scrollTop: $(link).offset().top - 15}, 300);
	return false;
}
function imgoverlay(overlayid, imgid, link) {
	$(imgid).attr('src', "/static/images/loading.gif");
	$(imgid).attr('src', link.href);
	$(overlayid).removeClass('overlay-hidden').addClass('overlay');
	return false;
}
function closeoverlay(overlayid) {
	if( window.panzoom ) {
		window.panzoom[0].style = "";
	}
	$(overlayid).removeClass('overlay').addClass('overlay-hidden');
	return false;
}

var init_boxcollapse = function() {
	$('div.box').each(function(i,box) {
		if(! $(box).hasClass('nocollapse') ) {
			if( document.documentElement.clientWidth <= 768 || $(box).hasClass('alwayscollapse') ) {
				$(box).addClass('collapsed');
			}
			$(box).children(':first').click(function(e) {
				$(box).toggleClass('collapsed');
				if(	!$(box).hasClass('collapsed') ) {
					if ( !$(box).is(':above-the-top') ) {
						$('html,body').animate({scrollTop: $(box).offset().top - 10}, 500);
					}
				}
			});
		}
	});
};

$(function() {
	init_boxcollapse();
	$('html').removeClass('no-js').addClass('js-on');
});
