angular.module('app', [])
.controller('TableController',
function TableController($scope, $http) {
  $scope.items = [];
  $http.get('/ajaxornot/view3-data')
  .success(function(response) {
    $scope.items = response.items;
  }).error(function() {
    console.error(arguments);
  });
  $scope.confirmAndGo = function(item) {
    if (confirm(item.title))
      window.location.href = '/plog/' + item.slug;
  };
});
