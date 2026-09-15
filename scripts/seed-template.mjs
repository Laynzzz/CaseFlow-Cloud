import {readFileSync} from 'node:fs';
import {client,signIn} from '../tests/e2e/oidc-session.mjs';

export async function seedTemplate(tenantId) {
  const token=await signIn('admin'),api=client(token),path=`/tenants/${tenantId}/templates`;
  const existing=(await api(path)).items.find(t=>t.name==='Standard purchase v1'&&t.state==='PUBLISHED');
  if(existing)return existing.id;
  const bytes=readFileSync(new URL('../infrastructure/local/generated/purchase-template.docx',import.meta.url));
  let template=await api(path,{method:'POST',body:{name:'Standard purchase v1',byteSize:bytes.length}});
  const response=await fetch(`http://127.0.0.1:8080/api/v1${path}/${template.id}/content`,{
    method:'PUT',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/octet-stream'},body:bytes,
  });
  if(!response.ok)throw new Error(`Synthetic template upload failed (${response.status})`);
  template=await api(`${path}/${template.id}/finalize`,{method:'POST',body:{expectedVersion:template.version}});
  template=await api(`${path}/${template.id}/publish`,{method:'POST',body:{expectedVersion:template.version}});
  return template.id;
}
