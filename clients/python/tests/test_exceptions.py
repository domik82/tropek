"""Tests for structured exception hierarchy and error parsing."""

from tropek_client.exceptions import (
    TropekAPIError,
    TropekConflictError,
    TropekConnectionError,
    TropekNotFoundError,
    TropekServerError,
    TropekValidationError,
    ValidationDetail,
    parse_error_response,
)


class TestExceptionHierarchy:
    def test_all_exceptions_inherit_from_base(self):
        for exc_class in [
            TropekNotFoundError,
            TropekConflictError,
            TropekValidationError,
            TropekServerError,
            TropekConnectionError,
        ]:
            assert issubclass(exc_class, TropekAPIError)

    def test_not_found_has_entity_and_name(self):
        exc = TropekNotFoundError(
            status_code=404,
            detail="asset 'my-svc' not found",
            entity='asset',
            name='my-svc',
        )
        assert exc.entity == 'asset'
        assert exc.name == 'my-svc'
        assert exc.status_code == 404

    def test_conflict_has_entity_name_reason(self):
        exc = TropekConflictError(
            status_code=409,
            detail="asset 'my-svc': already exists",
            entity='asset',
            name='my-svc',
            reason='already exists',
        )
        assert exc.reason == 'already exists'

    def test_validation_has_errors_list(self):
        errors = [ValidationDetail(loc=['body', 'name'], msg='field required', type='missing')]
        exc = TropekValidationError(status_code=422, detail='validation failed', errors=errors)
        assert len(exc.errors) == 1
        assert exc.errors[0].loc == ['body', 'name']


class TestParseErrorResponse:
    def test_parse_404(self):
        exc = parse_error_response(404, {'detail': "asset 'my-svc' not found"})
        assert isinstance(exc, TropekNotFoundError)
        assert exc.entity == 'asset'
        assert exc.name == 'my-svc'

    def test_parse_409(self):
        exc = parse_error_response(409, {'detail': "asset 'my-svc': already exists"})
        assert isinstance(exc, TropekConflictError)
        assert exc.entity == 'asset'
        assert exc.name == 'my-svc'
        assert exc.reason == 'already exists'

    def test_parse_422_with_detail_list(self):
        body = {'detail': [{'loc': ['body', 'name'], 'msg': 'field required', 'type': 'missing'}]}
        exc = parse_error_response(422, body)
        assert isinstance(exc, TropekValidationError)
        assert len(exc.errors) == 1

    def test_parse_422_with_string_detail(self):
        body = {'detail': 'some validation error'}
        exc = parse_error_response(422, body)
        assert isinstance(exc, TropekValidationError)

    def test_parse_500(self):
        exc = parse_error_response(500, {'detail': 'internal server error'})
        assert isinstance(exc, TropekServerError)

    def test_parse_unknown_status(self):
        exc = parse_error_response(503, {'detail': 'service unavailable'})
        assert isinstance(exc, TropekAPIError)

    def test_parse_404_unparseable_detail(self):
        exc = parse_error_response(404, {'detail': 'not found'})
        assert isinstance(exc, TropekNotFoundError)
        assert exc.entity is None
        assert exc.name is None
