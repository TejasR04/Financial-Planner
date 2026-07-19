from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.crypto import decrypt_secret, encrypt_secret
from app.domain.entities import Institution
from app.domain.enums import InstitutionStatus, ProviderType
from app.persistence.models import InstitutionModel
from app.persistence.repositories.base import BaseRepository


class InstitutionRepository(BaseRepository[InstitutionModel]):
    model = InstitutionModel

    async def name_map_for_user(self, user_id: UUID) -> dict[UUID, str]:
        """Return {institution_id: name} for every institution owned by the
        user. Used to enrich AccountResponse with a human-readable
        institution name without adding a persistence concern to the
        Account domain entity.
        """
        query = select(InstitutionModel.id, InstitutionModel.name).where(
            InstitutionModel.user_id == user_id
        )
        result = await self.session.execute(query)
        return {row.id: row.name for row in result.all()}

    async def get_by_external_item_id(self, external_item_id: str) -> InstitutionModel | None:
        query = select(InstitutionModel).where(InstitutionModel.external_item_id == external_item_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_from_plaid(
        self,
        user_id: UUID,
        name: str,
        external_item_id: str,
        access_token: str,
    ) -> Institution:
        """Persist a newly-linked Plaid Item. `access_token` is encrypted
        before it ever reaches the session/DB and the plaintext is never
        returned — callers get back the domain `Institution`, which has no
        token field at all.
        """
        row = InstitutionModel(
            id=uuid4(),
            user_id=user_id,
            name=name,
            provider=ProviderType.PLAID.value,
            status=InstitutionStatus.HEALTHY.value,
            external_item_id=external_item_id,
            plaid_access_token_encrypted=encrypt_secret(access_token),
        )
        self.session.add(row)
        await self.session.flush()
        return _to_domain(row)

    async def get_decrypted_access_token(self, institution_id: UUID) -> str:
        """Only call this from within PlaidProvider. Everywhere else should
        work with the domain Institution, which never carries the token."""
        row = await self._get_or_raise("Institution", institution_id)
        if row.plaid_access_token_encrypted is None:
            raise ValueError(f"Institution {institution_id} has no stored Plaid access token")
        return decrypt_secret(row.plaid_access_token_encrypted)


def _to_domain(row: InstitutionModel) -> Institution:
    return Institution(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        provider=ProviderType(row.provider),
        status=InstitutionStatus(row.status),
        last_synced_at=row.last_synced_at,
        external_item_id=row.external_item_id,
    )
